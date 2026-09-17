/*
 * SPDX-License-Identifier: MIT
 *
 * Dual-homed smart-grid backhaul: a 900 MHz store-and-forward chain and a
 * private LTE network reach the same edge routers.
 *
 * The network is read from a scenario file exported by `aisg ns3-export`; this
 * program only builds what the file declares. Everything is synthetic and every
 * parameter is nominal.
 *
 * Model summary
 *   - fibre, wired and 900 MHz hops: point-to-point links; radio hops carry a
 *     packet error model and a finite store-and-forward queue
 *   - private LTE: ns-3 LTE + EPC; each CPE is a UE
 *   - an edge router behind a CPE is reached through a NOC <-> CPE UDP tunnel,
 *     because the PGW only delivers downlink traffic to UE addresses
 *   - service addresses: NOC 10.255.0.1, site k 172.16.k.1 (on the loopback)
 *   - traffic per site: SCADA request/response polled from the NOC, and
 *     periodic telemetry from the edge router
 */

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/internet-module.h"
#include "ns3/lte-module.h"
#include "ns3/mobility-module.h"
#include "ns3/netanim-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/propagation-module.h"
#include "ns3/system-path.h"
#include "ns3/virtual-net-device.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("AisgDualHomedBackhaul");

namespace
{

const Ipv4Address kNocService("10.255.0.1");
const uint16_t kScadaPort = 5000;
const uint16_t kTelemetryPort = 6000;
const uint16_t kTelemetrySourcePort = 6001;

// ---------------------------------------------------------------------------
// event log: faults and route switches, in the order they happen
// ---------------------------------------------------------------------------
struct EventRecord
{
    double time;
    std::string subject;
    std::string what;
    std::string detail;
};

std::vector<EventRecord> g_events;

void
LogEvent(const std::string& subject, const std::string& what, const std::string& detail)
{
    g_events.push_back({Simulator::Now().GetSeconds(), subject, what, detail});
}

// ---------------------------------------------------------------------------
// scenario file
// ---------------------------------------------------------------------------
struct NodeSpec
{
    std::string id;
    std::string role;
    double x;
    double y;
};

struct LinkSpec
{
    std::string id;
    std::string a;
    std::string b;
    std::string cls;
    std::string rate;
    double delayMs;
    double per;
    std::string network;
    std::string rssi;
    std::string snr;
};

struct SiteSpec
{
    std::string er;
    std::string rm;
    std::string cpe;
    std::string primary;
    uint32_t index;
};

struct RouteSpec
{
    std::string node;
    std::string dest;
    std::string via;
};

struct PathSpec
{
    std::string er;
    std::string medium;
    std::string nocVia;
    std::string erVia;
};

struct FaultSpec
{
    double time;
    std::string kind;
    std::string target;
    std::string value;
};

struct FailoverSpec
{
    double time;
    std::string er;
    std::string medium;
};

struct Scenario
{
    std::map<std::string, std::string> params;
    std::vector<NodeSpec> nodes;
    std::vector<LinkSpec> links;
    std::vector<std::pair<std::string, std::string>> attachments;
    std::vector<SiteSpec> sites;
    std::vector<RouteSpec> routes;
    std::vector<PathSpec> paths;
    std::vector<FaultSpec> faults;
    std::vector<FailoverSpec> failovers;

    std::string Param(const std::string& name) const
    {
        auto it = params.find(name);
        NS_ABORT_MSG_IF(it == params.end(), "scenario is missing param " << name);
        return it->second;
    }

    double Number(const std::string& name) const
    {
        return std::stod(Param(name));
    }
};

Scenario
LoadScenario(const std::string& path)
{
    std::ifstream in(path);
    NS_ABORT_MSG_IF(!in, "cannot open scenario file " << path);
    Scenario s;
    std::string line;
    bool header = false;
    uint32_t number = 0;
    while (std::getline(in, line))
    {
        ++number;
        if (!line.empty() && line.back() == '\r')
        {
            line.pop_back();
        }
        auto hash = line.find('#');
        if (hash != std::string::npos)
        {
            line = line.substr(0, hash);
        }
        std::istringstream ss(line);
        std::string kind;
        if (!(ss >> kind))
        {
            continue;
        }
        if (!header)
        {
            std::string version;
            ss >> version;
            NS_ABORT_MSG_IF(kind != "aisg-ns3-scenario" || version != "1",
                            "unsupported scenario format at line " << number);
            header = true;
            continue;
        }
        if (kind == "param")
        {
            std::string name;
            std::string value;
            ss >> name >> value;
            s.params[name] = value;
        }
        else if (kind == "node")
        {
            NodeSpec n;
            ss >> n.id >> n.role >> n.x >> n.y;
            s.nodes.push_back(n);
        }
        else if (kind == "p2p")
        {
            LinkSpec l;
            ss >> l.id >> l.a >> l.b >> l.cls >> l.rate >> l.delayMs >> l.per >> l.network >>
                l.rssi >> l.snr;
            s.links.push_back(l);
        }
        else if (kind == "attach")
        {
            std::string cpe;
            std::string enb;
            ss >> cpe >> enb;
            s.attachments.emplace_back(cpe, enb);
        }
        else if (kind == "site")
        {
            SiteSpec site;
            ss >> site.er >> site.rm >> site.cpe >> site.primary >> site.index;
            s.sites.push_back(site);
        }
        else if (kind == "route")
        {
            RouteSpec r;
            ss >> r.node >> r.dest >> r.via;
            s.routes.push_back(r);
        }
        else if (kind == "path")
        {
            PathSpec p;
            ss >> p.er >> p.medium >> p.nocVia >> p.erVia;
            s.paths.push_back(p);
        }
        else if (kind == "fault")
        {
            FaultSpec f;
            ss >> f.time >> f.kind >> f.target >> f.value;
            s.faults.push_back(f);
        }
        else if (kind == "failover")
        {
            FailoverSpec f;
            ss >> f.time >> f.er >> f.medium;
            s.failovers.push_back(f);
        }
        else
        {
            NS_ABORT_MSG("unknown record '" << kind << "' at line " << number);
        }
        NS_ABORT_MSG_IF(ss.fail(), "malformed '" << kind << "' record at line " << number);
    }
    NS_ABORT_MSG_IF(!header, "scenario file " << path << " is empty");
    return s;
}

Ipv4Address
Dotted(const std::string& prefix, uint32_t index, const std::string& suffix)
{
    std::ostringstream out;
    out << prefix << index << suffix;
    return Ipv4Address(out.str().c_str());
}

// ---------------------------------------------------------------------------
// payloads
// ---------------------------------------------------------------------------
Ptr<Packet>
MakePayload(uint32_t sequence, uint32_t size)
{
    std::vector<uint8_t> buffer(std::max<uint32_t>(size, 4), 0);
    buffer[0] = static_cast<uint8_t>(sequence >> 24);
    buffer[1] = static_cast<uint8_t>(sequence >> 16);
    buffer[2] = static_cast<uint8_t>(sequence >> 8);
    buffer[3] = static_cast<uint8_t>(sequence);
    return Create<Packet>(buffer.data(), buffer.size());
}

uint32_t
ReadSequence(Ptr<const Packet> packet)
{
    uint8_t b[4] = {0, 0, 0, 0};
    packet->CopyData(b, 4);
    return (uint32_t(b[0]) << 24) | (uint32_t(b[1]) << 16) | (uint32_t(b[2]) << 8) | b[3];
}

// ---------------------------------------------------------------------------
// NOC <-> CPE tunnels
// ---------------------------------------------------------------------------
class TunnelHub
{
  public:
    TunnelHub(Ptr<Node> noc, uint16_t port)
    {
        m_socket = Socket::CreateSocket(noc, UdpSocketFactory::GetTypeId());
        m_socket->Bind(InetSocketAddress(Ipv4Address::GetAny(), port));
        m_socket->SetRecvCallback(MakeCallback(&TunnelHub::OnReceive, this));
    }

    Ptr<Socket> GetSocket() const
    {
        return m_socket;
    }

    void Register(Ipv4Address ueAddress, Ptr<VirtualNetDevice> tap)
    {
        m_tapByUe[ueAddress] = tap;
    }

  private:
    void OnReceive(Ptr<Socket> socket)
    {
        Address from;
        Ptr<Packet> packet;
        while ((packet = socket->RecvFrom(from)))
        {
            auto it = m_tapByUe.find(InetSocketAddress::ConvertFrom(from).GetIpv4());
            if (it != m_tapByUe.end())
            {
                it->second->Receive(packet,
                                    0x0800,
                                    it->second->GetAddress(),
                                    it->second->GetAddress(),
                                    NetDevice::PACKET_HOST);
            }
        }
    }

    Ptr<Socket> m_socket;
    std::map<Ipv4Address, Ptr<VirtualNetDevice>> m_tapByUe;
};

class SiteTunnel
{
  public:
    SiteTunnel(TunnelHub& hub,
               Ptr<Node> noc,
               Ptr<Node> cpe,
               Ipv4Address ueAddress,
               Ipv4Address nocOuterAddress,
               uint32_t index,
               uint16_t port)
        : m_hubSocket(hub.GetSocket()),
          m_ueAddress(ueAddress),
          m_nocOuterAddress(nocOuterAddress),
          m_port(port)
    {
        m_nocInner = Dotted("11.", index, ".0.1");
        m_cpeInner = Dotted("11.", index, ".0.2");

        m_nocTap = CreateObject<VirtualNetDevice>();
        m_nocTap->SetAddress(Mac48Address::Allocate());
        m_nocTap->SetSendCallback(MakeCallback(&SiteTunnel::NocSend, this));
        noc->AddDevice(m_nocTap);
        Ptr<Ipv4> nocIp = noc->GetObject<Ipv4>();
        m_nocInterface = nocIp->AddInterface(m_nocTap);
        nocIp->AddAddress(m_nocInterface,
                          Ipv4InterfaceAddress(m_nocInner, Ipv4Mask("255.255.255.252")));
        nocIp->SetUp(m_nocInterface);

        m_cpeTap = CreateObject<VirtualNetDevice>();
        m_cpeTap->SetAddress(Mac48Address::Allocate());
        m_cpeTap->SetSendCallback(MakeCallback(&SiteTunnel::CpeSend, this));
        cpe->AddDevice(m_cpeTap);
        Ptr<Ipv4> cpeIp = cpe->GetObject<Ipv4>();
        m_cpeInterface = cpeIp->AddInterface(m_cpeTap);
        cpeIp->AddAddress(m_cpeInterface,
                          Ipv4InterfaceAddress(m_cpeInner, Ipv4Mask("255.255.255.252")));
        cpeIp->SetUp(m_cpeInterface);

        m_cpeSocket = Socket::CreateSocket(cpe, UdpSocketFactory::GetTypeId());
        m_cpeSocket->Bind(InetSocketAddress(Ipv4Address::GetAny(), port));
        m_cpeSocket->SetRecvCallback(MakeCallback(&SiteTunnel::CpeReceive, this));

        hub.Register(ueAddress, m_nocTap);
    }

    uint32_t NocInterface() const
    {
        return m_nocInterface;
    }

    uint32_t CpeInterface() const
    {
        return m_cpeInterface;
    }

    Ipv4Address NocInner() const
    {
        return m_nocInner;
    }

    Ipv4Address CpeInner() const
    {
        return m_cpeInner;
    }

  private:
    bool NocSend(Ptr<Packet> packet, const Address&, const Address&, uint16_t)
    {
        m_hubSocket->SendTo(packet, 0, InetSocketAddress(m_ueAddress, m_port));
        return true;
    }

    bool CpeSend(Ptr<Packet> packet, const Address&, const Address&, uint16_t)
    {
        m_cpeSocket->SendTo(packet, 0, InetSocketAddress(m_nocOuterAddress, m_port));
        return true;
    }

    void CpeReceive(Ptr<Socket> socket)
    {
        Ptr<Packet> packet;
        while ((packet = socket->Recv()))
        {
            m_cpeTap->Receive(packet,
                              0x0800,
                              m_cpeTap->GetAddress(),
                              m_cpeTap->GetAddress(),
                              NetDevice::PACKET_HOST);
        }
    }

    Ptr<Socket> m_hubSocket;
    Ptr<Socket> m_cpeSocket;
    Ptr<VirtualNetDevice> m_nocTap;
    Ptr<VirtualNetDevice> m_cpeTap;
    Ipv4Address m_ueAddress;
    Ipv4Address m_nocOuterAddress;
    Ipv4Address m_nocInner;
    Ipv4Address m_cpeInner;
    uint32_t m_nocInterface{0};
    uint32_t m_cpeInterface{0};
    uint16_t m_port;
};

// ---------------------------------------------------------------------------
// failover: swapping a site's host route at either end
// ---------------------------------------------------------------------------
struct Hop
{
    Ipv4Address nextHop;
    uint32_t interface;
};

class SiteRouter
{
  public:
    struct SiteRoutes
    {
        Ptr<Ipv4StaticRouting> nocTable;
        Ptr<Ipv4StaticRouting> erTable;
        Ipv4Address siteAddress;
        std::map<std::string, Hop> nocHop; // medium -> NOC next hop towards the site
        std::map<std::string, Hop> erHop;  // medium -> ER next hop towards the NOC
        std::string nocMedium;
        std::string erMedium;
    };

    void AddSite(const std::string& er, const SiteRoutes& routes)
    {
        m_sites[er] = routes;
    }

    const std::string& NocMedium(const std::string& er) const
    {
        return m_sites.at(er).nocMedium;
    }

    const std::string& ErMedium(const std::string& er) const
    {
        return m_sites.at(er).erMedium;
    }

    static std::string Other(const std::string& medium)
    {
        return medium == "plte" ? "radio900" : "plte";
    }

    void SwitchNoc(const std::string& er, const std::string& medium, const std::string& reason)
    {
        SiteRoutes& s = m_sites.at(er);
        if (s.nocMedium == medium)
        {
            return;
        }
        Replace(s.nocTable, s.siteAddress, s.nocHop.at(medium));
        LogEvent(er, "switch-noc", s.nocMedium + " -> " + medium + " (" + reason + ")");
        s.nocMedium = medium;
    }

    void SwitchEr(const std::string& er, const std::string& medium, const std::string& reason)
    {
        SiteRoutes& s = m_sites.at(er);
        if (s.erMedium == medium)
        {
            return;
        }
        Replace(s.erTable, kNocService, s.erHop.at(medium));
        LogEvent(er, "switch-er", s.erMedium + " -> " + medium + " (" + reason + ")");
        s.erMedium = medium;
    }

  private:
    static void Replace(Ptr<Ipv4StaticRouting> table, Ipv4Address dest, const Hop& hop)
    {
        for (uint32_t i = table->GetNRoutes(); i-- > 0;)
        {
            Ipv4RoutingTableEntry entry = table->GetRoute(i);
            if (entry.IsHost() && entry.GetDest() == dest)
            {
                table->RemoveRoute(i);
            }
        }
        table->AddHostRouteTo(dest, hop.nextHop, hop.interface);
    }

    std::map<std::string, SiteRoutes> m_sites;
};

// ---------------------------------------------------------------------------
// traffic
// ---------------------------------------------------------------------------
struct TrafficConfig
{
    Time start;
    Time stop;
    Time scadaInterval;
    Time telemetryInterval;
    uint32_t requestBytes;
    uint32_t responseBytes;
    uint32_t telemetryBytes;
};

class SiteTraffic
{
  public:
    SiteTraffic(const SiteSpec& spec,
                Ipv4Address siteAddress,
                Ptr<Node> noc,
                Ptr<Node> er,
                const TrafficConfig& config,
                SiteRouter* router,
                bool localFailover,
                uint32_t missThreshold)
        : m_spec(spec),
          m_address(siteAddress),
          m_config(config),
          m_router(router),
          m_localFailover(localFailover),
          m_missThreshold(missThreshold),
          m_lastPollAtEr(config.start)
    {
        m_nocPoll = Socket::CreateSocket(noc, UdpSocketFactory::GetTypeId());
        m_nocPoll->Bind(InetSocketAddress(kNocService, static_cast<uint16_t>(20000 + spec.index)));
        m_nocPoll->SetRecvCallback(MakeCallback(&SiteTraffic::OnReply, this));

        m_erResponder = Socket::CreateSocket(er, UdpSocketFactory::GetTypeId());
        m_erResponder->Bind(InetSocketAddress(m_address, kScadaPort));
        m_erResponder->SetRecvCallback(MakeCallback(&SiteTraffic::OnRequest, this));

        m_erTelemetry = Socket::CreateSocket(er, UdpSocketFactory::GetTypeId());
        m_erTelemetry->Bind(InetSocketAddress(m_address, kTelemetrySourcePort));

        // Stagger the sites so their packets do not all leave in the same instant.
        Simulator::Schedule(config.start + MilliSeconds(37 * spec.index % 1000),
                            &SiteTraffic::Poll,
                            this);
        Simulator::Schedule(config.start + MilliSeconds(53 * spec.index % 1000),
                            &SiteTraffic::SendTelemetry,
                            this);
        Simulator::Schedule(config.start +
                                Seconds(config.scadaInterval.GetSeconds() * missThreshold),
                            &SiteTraffic::WatchPolls,
                            this);
    }

    const SiteSpec& Spec() const
    {
        return m_spec;
    }

    Ipv4Address ServiceAddress() const
    {
        return m_address;
    }

    void CountTelemetry()
    {
        ++m_telemetryReceived;
    }

    void WriteCsvRow(std::ostream& out) const
    {
        double loss = m_scadaSent ? 100.0 * (m_scadaSent - m_scadaReceived) / m_scadaSent : 0.0;
        double mean = m_scadaReceived ? m_rttSumMs / m_scadaReceived : 0.0;
        out << m_spec.index << ',' << m_spec.er << ',' << m_spec.primary << ',' << m_scadaSent
            << ',' << m_scadaReceived << ',' << std::fixed << std::setprecision(2) << loss << ','
            << mean << ',' << m_rttMaxMs << ',' << m_telemetrySent << ',' << m_telemetryReceived
            << ',' << m_router->NocMedium(m_spec.er) << ',' << m_router->ErMedium(m_spec.er)
            << '\n';
        out.unsetf(std::ios::fixed);
    }

    void WriteRequests(std::ostream& out) const
    {
        for (std::size_t i = 0; i < m_sentAt.size(); ++i)
        {
            out << m_spec.er << ',' << i << ',' << m_sentAt[i] << ',';
            if (m_rttMs[i] >= 0.0)
            {
                out << m_rttMs[i];
            }
            out << '\n';
        }
    }

  private:
    void Poll()
    {
        if (Simulator::Now() >= m_config.stop)
        {
            return;
        }
        uint32_t sequence = m_sequence++;
        m_pending[sequence] = Simulator::Now();
        m_sentAt.push_back(Simulator::Now().GetSeconds());
        m_rttMs.push_back(-1.0);
        m_nocPoll->SendTo(MakePayload(sequence, m_config.requestBytes),
                          0,
                          InetSocketAddress(m_address, kScadaPort));
        ++m_scadaSent;
        Simulator::Schedule(m_config.scadaInterval, &SiteTraffic::CheckReply, this, sequence);
        Simulator::Schedule(m_config.scadaInterval, &SiteTraffic::Poll, this);
    }

    // A reply that has not arrived within one polling interval is a miss. With
    // local failover, the NOC moves the site's downlink to the other medium
    // after enough consecutive misses.
    void CheckReply(uint32_t sequence)
    {
        auto it = m_pending.find(sequence);
        if (it == m_pending.end())
        {
            return;
        }
        m_pending.erase(it);
        ++m_misses;
        if (m_localFailover && m_misses >= m_missThreshold)
        {
            m_router->SwitchNoc(m_spec.er,
                                SiteRouter::Other(m_router->NocMedium(m_spec.er)),
                                "local: " + std::to_string(m_misses) + " missed replies");
            m_misses = 0;
        }
    }

    // With local failover, an edge router that stops hearing polls moves its
    // uplink to the other medium.
    void WatchPolls()
    {
        if (Simulator::Now() >= m_config.stop)
        {
            return;
        }
        Time limit = Seconds(m_config.scadaInterval.GetSeconds() * m_missThreshold);
        if (m_localFailover && Simulator::Now() - m_lastPollAtEr > limit)
        {
            m_router->SwitchEr(m_spec.er,
                               SiteRouter::Other(m_router->ErMedium(m_spec.er)),
                               "local: no poll for " +
                                   std::to_string(
                                       (Simulator::Now() - m_lastPollAtEr).GetSeconds()) +
                                   " s");
            m_lastPollAtEr = Simulator::Now();
        }
        Simulator::Schedule(m_config.scadaInterval, &SiteTraffic::WatchPolls, this);
    }

    void OnRequest(Ptr<Socket> socket)
    {
        Address from;
        Ptr<Packet> packet;
        while ((packet = socket->RecvFrom(from)))
        {
            if (packet->GetSize() >= 4)
            {
                m_lastPollAtEr = Simulator::Now();
                socket->SendTo(MakePayload(ReadSequence(packet), m_config.responseBytes), 0, from);
            }
        }
    }

    void OnReply(Ptr<Socket> socket)
    {
        Ptr<Packet> packet;
        while ((packet = socket->Recv()))
        {
            uint32_t sequence = ReadSequence(packet);
            auto it = m_pending.find(sequence);
            if (it == m_pending.end())
            {
                continue; // unknown, duplicate, or arrived after its timeout
            }
            double rtt = (Simulator::Now() - it->second).GetSeconds() * 1e3;
            m_pending.erase(it);
            ++m_scadaReceived;
            m_rttSumMs += rtt;
            m_rttMaxMs = std::max(m_rttMaxMs, rtt);
            m_rttMs[sequence] = rtt;
            m_misses = 0;
        }
    }

    void SendTelemetry()
    {
        if (Simulator::Now() >= m_config.stop)
        {
            return;
        }
        ++m_telemetrySent;
        m_erTelemetry->SendTo(MakePayload(m_telemetrySent, m_config.telemetryBytes),
                              0,
                              InetSocketAddress(kNocService, kTelemetryPort));
        Simulator::Schedule(m_config.telemetryInterval, &SiteTraffic::SendTelemetry, this);
    }

    SiteSpec m_spec;
    Ipv4Address m_address;
    TrafficConfig m_config;
    SiteRouter* m_router;
    bool m_localFailover;
    uint32_t m_missThreshold;
    Time m_lastPollAtEr;
    uint32_t m_misses{0};
    std::vector<double> m_sentAt;
    std::vector<double> m_rttMs;
    Ptr<Socket> m_nocPoll;
    Ptr<Socket> m_erResponder;
    Ptr<Socket> m_erTelemetry;
    uint32_t m_sequence{0};
    std::map<uint32_t, Time> m_pending;
    uint64_t m_scadaSent{0};
    uint64_t m_scadaReceived{0};
    uint64_t m_telemetrySent{0};
    uint64_t m_telemetryReceived{0};
    double m_rttSumMs{0.0};
    double m_rttMaxMs{0.0};
};

class TelemetrySink
{
  public:
    TelemetrySink(Ptr<Node> noc)
    {
        m_socket = Socket::CreateSocket(noc, UdpSocketFactory::GetTypeId());
        m_socket->Bind(InetSocketAddress(kNocService, kTelemetryPort));
        m_socket->SetRecvCallback(MakeCallback(&TelemetrySink::OnReceive, this));
    }

    void Register(SiteTraffic* site)
    {
        m_siteByAddress[site->ServiceAddress()] = site;
    }

  private:
    void OnReceive(Ptr<Socket> socket)
    {
        Address from;
        Ptr<Packet> packet;
        while ((packet = socket->RecvFrom(from)))
        {
            auto it = m_siteByAddress.find(InetSocketAddress::ConvertFrom(from).GetIpv4());
            if (it != m_siteByAddress.end())
            {
                it->second->CountTelemetry();
            }
        }
    }

    Ptr<Socket> m_socket;
    std::map<Ipv4Address, SiteTraffic*> m_siteByAddress;
};

// ---------------------------------------------------------------------------
// building blocks
// ---------------------------------------------------------------------------
struct Endpoint
{
    uint32_t interface;
    Ipv4Address address;
};

double
HeightFor(const std::string& role)
{
    if (role == "enb")
    {
        return 30.0;
    }
    if (role == "cpe" || role == "rm")
    {
        return 6.0;
    }
    return 10.0;
}

void
AddServiceAddress(Ptr<Node> node, Ipv4Address address)
{
    // Interface 0 is the loopback. With the weak end-system model, a packet
    // arriving on any interface is delivered locally when its destination is
    // any of the node's addresses, so the service address is reachable over
    // either access network.
    node->GetObject<Ipv4>()->AddAddress(
        0,
        Ipv4InterfaceAddress(address, Ipv4Mask("255.255.255.255")));
}

} // namespace

int
main(int argc, char* argv[])
{
    std::string scenarioPath;
    std::string outDir = "aisg-ns3-output";
    double simTimeOverride = 0.0;
    uint32_t earfcnDlOverride = 0;
    uint32_t earfcnUlOverride = 0;
    bool animate = false;
    double cpeGainOverride = -999.0;
    std::string failover = "none";

    CommandLine cmd(__FILE__);
    cmd.AddValue("cpeGain", "override the CPE antenna boresight gain, in dBi", cpeGainOverride);
    cmd.AddValue("failover", "none | local | central", failover);
    cmd.AddValue("scenario", "scenario file exported by `aisg ns3-export`", scenarioPath);
    cmd.AddValue("outDir", "directory for results", outDir);
    cmd.AddValue("simTime", "override the simulated time, in seconds", simTimeOverride);
    cmd.AddValue("earfcnDl", "override the LTE downlink EARFCN", earfcnDlOverride);
    cmd.AddValue("earfcnUl", "override the LTE uplink EARFCN", earfcnUlOverride);
    cmd.AddValue("animate", "write a NetAnim trace", animate);
    cmd.Parse(argc, argv);
    NS_ABORT_MSG_IF(scenarioPath.empty(), "--scenario is required");
    NS_ABORT_MSG_IF(failover != "none" && failover != "local" && failover != "central",
                    "--failover must be none, local or central");

    Scenario scenario = LoadScenario(scenarioPath);
    SystemPath::MakeDirectories(outDir);
    double simTime = simTimeOverride > 0 ? simTimeOverride : scenario.Number("sim_time_s");

    // --- LTE configuration (before any LTE object exists) -------------------
    uint32_t earfcnDl = earfcnDlOverride ? earfcnDlOverride
                                         : static_cast<uint32_t>(scenario.Number("lte_earfcn_dl"));
    uint32_t earfcnUl = earfcnUlOverride ? earfcnUlOverride
                                         : static_cast<uint32_t>(scenario.Number("lte_earfcn_ul"));
    auto bandwidth = static_cast<uint16_t>(scenario.Number("lte_bandwidth_rb"));
    Config::SetDefault("ns3::LteEnbNetDevice::DlEarfcn", UintegerValue(earfcnDl));
    Config::SetDefault("ns3::LteEnbNetDevice::UlEarfcn", UintegerValue(earfcnUl));
    Config::SetDefault("ns3::LteUeNetDevice::DlEarfcn", UintegerValue(earfcnDl));
    Config::SetDefault("ns3::LteEnbNetDevice::DlBandwidth", UintegerValue(bandwidth));
    Config::SetDefault("ns3::LteEnbNetDevice::UlBandwidth", UintegerValue(bandwidth));
    Config::SetDefault("ns3::LteEnbPhy::TxPower", DoubleValue(scenario.Number("enb_tx_power_dbm")));
    Config::SetDefault("ns3::LteUePhy::TxPower", DoubleValue(scenario.Number("ue_tx_power_dbm")));

    Ptr<LteHelper> lteHelper = CreateObject<LteHelper>();
    Ptr<PointToPointEpcHelper> epcHelper = CreateObject<PointToPointEpcHelper>();
    lteHelper->SetEpcHelper(epcHelper);
    lteHelper->SetAttribute("PathlossModel", StringValue("ns3::OkumuraHataPropagationLossModel"));
    lteHelper->SetPathlossModelAttribute("Frequency",
                                         DoubleValue(scenario.Number("lte_dl_frequency_hz")));
    lteHelper->SetPathlossModelAttribute("Environment", EnumValue(SubUrbanEnvironment));
    lteHelper->SetPathlossModelAttribute("CitySize", EnumValue(SmallCity));

    // A fixed outdoor CPE uses a directional antenna aimed at its serving
    // eNodeB; each one is oriented after the UE devices exist.
    double cpeGain = cpeGainOverride > -900.0 ? cpeGainOverride
                                             : scenario.Number("cpe_antenna_max_gain_dbi");
    lteHelper->SetUeAntennaModelType("ns3::CosineAntennaModel");
    lteHelper->SetUeAntennaModelAttribute("MaxGain", DoubleValue(cpeGain));
    lteHelper->SetUeAntennaModelAttribute(
        "HorizontalBeamwidth",
        DoubleValue(scenario.Number("cpe_antenna_beamwidth_deg")));

    // --- nodes -------------------------------------------------------------
    std::map<std::string, Ptr<Node>> nodes;
    std::map<std::string, std::string> roles;
    std::map<std::string, const NodeSpec*> specById;
    NodeContainer enbNodes;
    NodeContainer cpeNodes;
    NodeContainer ipNodes;
    for (const auto& spec : scenario.nodes)
    {
        Ptr<Node> node = CreateObject<Node>();
        nodes[spec.id] = node;
        roles[spec.id] = spec.role;
        specById[spec.id] = &spec;
        Ptr<ConstantPositionMobilityModel> position =
            CreateObject<ConstantPositionMobilityModel>();
        position->SetPosition(Vector(spec.x, spec.y, HeightFor(spec.role)));
        node->AggregateObject(position);
        if (spec.role == "enb")
        {
            enbNodes.Add(node);
        }
        else
        {
            ipNodes.Add(node);
            if (spec.role == "cpe")
            {
                cpeNodes.Add(node);
            }
        }
    }
    auto node = [&nodes](const std::string& id) {
        auto it = nodes.find(id);
        NS_ABORT_MSG_IF(it == nodes.end(), "unknown node " << id);
        return it->second;
    };
    Ptr<Node> noc;
    std::string nocId;
    for (const auto& [id, role] : roles)
    {
        if (role == "noc")
        {
            noc = nodes[id];
            nocId = id;
        }
    }
    NS_ABORT_MSG_IF(!noc, "scenario declares no NOC");

    InternetStackHelper internet;
    internet.Install(ipNodes);

    // --- fibre, wired and 900 MHz links ---------------------------------------
    std::map<std::pair<std::string, std::string>, std::pair<Endpoint, Endpoint>> adjacency;
    std::map<std::string, Ptr<RateErrorModel>> radioErrorModels;
    std::string radioQueue = scenario.Param("radio_queue_packets") + "p";
    for (const auto& link : scenario.links)
    {
        PointToPointHelper p2p;
        p2p.SetDeviceAttribute("DataRate", DataRateValue(DataRate(link.rate)));
        p2p.SetChannelAttribute("Delay",
                                TimeValue(MicroSeconds(std::llround(link.delayMs * 1000.0))));
        if (link.cls == "radio")
        {
            p2p.SetQueue("ns3::DropTailQueue<Packet>", "MaxSize", StringValue(radioQueue));
        }
        NetDeviceContainer devices = p2p.Install(node(link.a), node(link.b));
        if (link.cls == "radio")
        {
            for (uint32_t i = 0; i < 2; ++i)
            {
                Ptr<RateErrorModel> em = CreateObject<RateErrorModel>();
                em->SetUnit(RateErrorModel::ERROR_UNIT_PACKET);
                em->SetRate(link.per);
                DynamicCast<PointToPointNetDevice>(devices.Get(i))->SetReceiveErrorModel(em);
                radioErrorModels[link.id + "@" + (i == 0 ? link.a : link.b)] = em;
            }
        }
        Ipv4AddressHelper addresses;
        addresses.SetBase(Ipv4Address(link.network.c_str()), Ipv4Mask("255.255.255.0"));
        Ipv4InterfaceContainer interfaces = addresses.Assign(devices);
        Endpoint ea{interfaces.Get(0).second, interfaces.GetAddress(0)};
        Endpoint eb{interfaces.Get(1).second, interfaces.GetAddress(1)};
        adjacency[{link.a, link.b}] = {ea, eb};
        adjacency[{link.b, link.a}] = {eb, ea};
    }

    // --- service addresses ---------------------------------------------------
    AddServiceAddress(noc, kNocService);
    std::map<std::string, Ipv4Address> siteAddress;
    std::map<std::string, const SiteSpec*> siteByEr;
    std::map<std::string, const SiteSpec*> siteByCpe;
    for (const auto& site : scenario.sites)
    {
        siteAddress[site.er] = Dotted("172.16.", site.index, ".1");
        siteByEr[site.er] = &site;
        siteByCpe[site.cpe] = &site;
        AddServiceAddress(node(site.er), siteAddress[site.er]);
    }

    // --- private LTE -----------------------------------------------------------
    Ptr<Node> pgw = epcHelper->GetPgwNode();
    PointToPointHelper core;
    core.SetDeviceAttribute("DataRate", DataRateValue(DataRate("10Gbps")));
    core.SetChannelAttribute("Delay", TimeValue(MilliSeconds(1)));
    NetDeviceContainer coreDevices = core.Install(noc, pgw);
    Ipv4AddressHelper coreAddresses;
    coreAddresses.SetBase("10.254.0.0", "255.255.255.0");
    Ipv4InterfaceContainer coreInterfaces = coreAddresses.Assign(coreDevices);
    Ipv4Address nocOuterAddress = coreInterfaces.GetAddress(0);

    Ipv4StaticRoutingHelper routing;
    routing.GetStaticRouting(noc->GetObject<Ipv4>())
        ->AddNetworkRouteTo(Ipv4Address("7.0.0.0"),
                            Ipv4Mask("255.0.0.0"),
                            coreInterfaces.GetAddress(1),
                            coreInterfaces.Get(0).second);

    NetDeviceContainer enbDevices = lteHelper->InstallEnbDevice(enbNodes);
    NetDeviceContainer ueDevices = lteHelper->InstallUeDevice(cpeNodes);
    Ipv4InterfaceContainer ueInterfaces = epcHelper->AssignUeIpv4Address(ueDevices);

    std::map<std::string, Ptr<NetDevice>> enbDeviceById;
    for (uint32_t i = 0; i < enbNodes.GetN(); ++i)
    {
        for (const auto& [id, n] : nodes)
        {
            if (n == enbNodes.Get(i))
            {
                enbDeviceById[id] = enbDevices.Get(i);
            }
        }
    }
    std::map<std::string, Ptr<NetDevice>> ueDeviceById;
    std::map<std::string, Ipv4Address> ueAddressById;
    for (uint32_t i = 0; i < cpeNodes.GetN(); ++i)
    {
        for (const auto& [id, n] : nodes)
        {
            if (n == cpeNodes.Get(i))
            {
                ueDeviceById[id] = ueDevices.Get(i);
                ueAddressById[id] = ueInterfaces.GetAddress(i);
            }
        }
        Ptr<Ipv4> ipv4 = cpeNodes.Get(i)->GetObject<Ipv4>();
        int32_t lteInterface = ipv4->GetInterfaceForDevice(ueDevices.Get(i));
        routing.GetStaticRouting(ipv4)->SetDefaultRoute(epcHelper->GetUeDefaultGatewayAddress(),
                                                        lteInterface);
    }
    for (const auto& [cpe, enb] : scenario.attachments)
    {
        NS_ABORT_MSG_IF(!ueDeviceById.count(cpe) || !enbDeviceById.count(enb),
                        "cannot attach " << cpe << " to " << enb);
        // Aim the CPE antenna at its serving eNodeB. The UE's downlink and
        // uplink share one antenna object, so one orientation covers both.
        const NodeSpec* from = specById.at(cpe);
        const NodeSpec* to = specById.at(enb);
        double azimuthDeg = std::atan2(to->y - from->y, to->x - from->x) * 180.0 / 3.141592653589793;
        DynamicCast<LteUeNetDevice>(ueDeviceById[cpe])
            ->GetPhy()
            ->GetDlSpectrumPhy()
            ->GetAntenna()
            ->SetAttribute("Orientation", DoubleValue(azimuthDeg));
        lteHelper->Attach(ueDeviceById[cpe], enbDeviceById[enb]);
    }

    // --- tunnels -----------------------------------------------------------------
    uint16_t tunnelPort = static_cast<uint16_t>(scenario.Number("tunnel_port"));
    TunnelHub hub(noc, tunnelPort);
    std::map<std::string, std::unique_ptr<SiteTunnel>> tunnelByEr;
    for (const auto& site : scenario.sites)
    {
        tunnelByEr[site.er] = std::make_unique<SiteTunnel>(hub,
                                                           noc,
                                                           node(site.cpe),
                                                           ueAddressById.at(site.cpe),
                                                           nocOuterAddress,
                                                           site.index,
                                                           tunnelPort);
    }

    // --- static routes -----------------------------------------------------------
    for (const auto& route : scenario.routes)
    {
        Ptr<Ipv4StaticRouting> table = routing.GetStaticRouting(node(route.node)->GetObject<Ipv4>());
        Ipv4Address dest = route.dest == "noc" ? kNocService : siteAddress.at(route.dest);
        if (route.via == "tunnel")
        {
            if (route.node == "NOC" || roles[route.node] == "noc")
            {
                const SiteTunnel& tunnel = *tunnelByEr.at(route.dest);
                table->AddHostRouteTo(dest, tunnel.CpeInner(), tunnel.NocInterface());
            }
            else
            {
                const SiteSpec* site = siteByCpe.at(route.node);
                const SiteTunnel& tunnel = *tunnelByEr.at(site->er);
                table->AddHostRouteTo(dest, tunnel.NocInner(), tunnel.CpeInterface());
            }
            continue;
        }
        auto it = adjacency.find({route.node, route.via});
        NS_ABORT_MSG_IF(it == adjacency.end(),
                        "route " << route.node << " -> " << route.via << " is not a link");
        table->AddHostRouteTo(dest, it->second.second.address, it->second.first.interface);
    }

    // --- per-site routes on both media, for failover ----------------------------------
    SiteRouter router;
    std::map<std::string, std::map<std::string, const PathSpec*>> pathBySite;
    for (const auto& path : scenario.paths)
    {
        pathBySite[path.er][path.medium] = &path;
    }
    for (const auto& site : scenario.sites)
    {
        SiteRouter::SiteRoutes routes;
        routes.nocTable = routing.GetStaticRouting(noc->GetObject<Ipv4>());
        routes.erTable = routing.GetStaticRouting(node(site.er)->GetObject<Ipv4>());
        routes.siteAddress = siteAddress.at(site.er);
        const SiteTunnel& tunnel = *tunnelByEr.at(site.er);
        for (const auto& [medium, path] : pathBySite[site.er])
        {
            if (path->nocVia == "tunnel")
            {
                routes.nocHop[medium] = Hop{tunnel.CpeInner(), tunnel.NocInterface()};
            }
            else
            {
                const auto& ends = adjacency.at({nocId, path->nocVia});
                routes.nocHop[medium] = Hop{ends.second.address, ends.first.interface};
            }
            const auto& ends = adjacency.at({site.er, path->erVia});
            routes.erHop[medium] = Hop{ends.second.address, ends.first.interface};
        }
        NS_ABORT_MSG_IF(routes.nocHop.size() != 2 || routes.erHop.size() != 2,
                        site.er << " needs a path on both media");
        routes.nocMedium = site.primary;
        routes.erMedium = site.primary;
        router.AddSite(site.er, routes);
    }

    // --- faults --------------------------------------------------------------------------
    for (const auto& fault : scenario.faults)
    {
        Time at = Seconds(fault.time);
        std::string subject = fault.target;
        if (fault.kind == "node_down")
        {
            Ptr<Node> target = node(fault.target);
            Simulator::Schedule(at, [target, subject]() {
                Ptr<Ipv4> ipv4 = target->GetObject<Ipv4>();
                for (uint32_t i = 1; i < ipv4->GetNInterfaces(); ++i)
                {
                    ipv4->SetDown(i);
                }
                LogEvent(subject, "fault", "node_down");
            });
        }
        else if (fault.kind == "radio_per")
        {
            std::vector<Ptr<RateErrorModel>> models;
            for (const auto& [key, model] : radioErrorModels)
            {
                if (key.rfind(fault.target + "@", 0) == 0)
                {
                    models.push_back(model);
                }
            }
            NS_ABORT_MSG_IF(models.empty(), "fault on unknown radio link " << fault.target);
            double rate = std::stod(fault.value);
            Simulator::Schedule(at, [models, rate, subject]() {
                for (const auto& model : models)
                {
                    model->SetRate(rate);
                }
                LogEvent(subject, "fault", "radio_per " + std::to_string(rate));
            });
        }
        else if (fault.kind == "flood")
        {
            for (const auto& [cpe, enb] : scenario.attachments)
            {
                if (enb != fault.target)
                {
                    continue;
                }
                PacketSinkHelper sink("ns3::UdpSocketFactory",
                                      InetSocketAddress(Ipv4Address::GetAny(), 9));
                sink.Install(node(cpe)).Start(Seconds(0));
                OnOffHelper flood("ns3::UdpSocketFactory",
                                  InetSocketAddress(ueAddressById.at(cpe), 9));
                flood.SetConstantRate(DataRate(fault.value), 1400);
                ApplicationContainer app = flood.Install(noc);
                app.Start(at);
                app.Stop(Seconds(simTime));
            }
            std::string value = fault.value;
            Simulator::Schedule(at, [subject, value]() {
                LogEvent(subject, "fault", "flood " + value + " to each attached CPE");
            });
        }
        else
        {
            NS_ABORT_MSG("unknown fault kind " << fault.kind);
        }
    }

    if (failover == "central")
    {
        for (const auto& plan : scenario.failovers)
        {
            std::string er = plan.er;
            std::string medium = plan.medium;
            Simulator::Schedule(Seconds(plan.time), [&router, er, medium]() {
                router.SwitchNoc(er, medium, "central: blackboard plan");
                router.SwitchEr(er, medium, "central: blackboard plan");
            });
        }
    }

    // --- traffic -------------------------------------------------------------------
    TrafficConfig config{Seconds(scenario.Number("traffic_start_s")),
                         Seconds(simTime - 1.0),
                         Seconds(scenario.Number("scada_interval_s")),
                         Seconds(scenario.Number("telemetry_interval_s")),
                         static_cast<uint32_t>(scenario.Number("scada_request_bytes")),
                         static_cast<uint32_t>(scenario.Number("scada_response_bytes")),
                         static_cast<uint32_t>(scenario.Number("telemetry_bytes"))};
    TelemetrySink sink(noc);
    std::vector<std::unique_ptr<SiteTraffic>> traffic;
    for (const auto& site : scenario.sites)
    {
        traffic.push_back(std::make_unique<SiteTraffic>(
            site,
            siteAddress.at(site.er),
            noc,
            node(site.er),
            config,
            &router,
            failover == "local",
            static_cast<uint32_t>(scenario.Number("local_miss_threshold"))));
        sink.Register(traffic.back().get());
    }

    FlowMonitorHelper flowHelper;
    Ptr<FlowMonitor> monitor = flowHelper.InstallAll();

    std::unique_ptr<AnimationInterface> animation;
    if (animate)
    {
        // PointToPointEpcHelper creates the SGW, PGW and MME itself, so they are
        // absent from the scenario file and never receive a position: NetAnim warns
        // about them and stacks them on the NOC at the origin. The declared topology
        // spans x 0..25000, so negative x keeps them clear of every real node. This
        // has to run before the AnimationInterface exists.
        double epcY = 2400.0;
        for (auto it = NodeList::Begin(); it != NodeList::End(); ++it)
        {
            if ((*it)->GetObject<MobilityModel>() == nullptr)
            {
                AnimationInterface::SetConstantPosition(*it, -3000.0, epcY);
                epcY -= 2400.0;
            }
        }

        // The palette the repository's own figures use, so both agree on colour.
        const std::map<std::string, std::array<uint8_t, 3>> colours = {
            {"noc", {{27, 58, 107}}},   {"enb", {{63, 124, 172}}},
            {"cpe", {{193, 102, 107}}}, {"rm", {{107, 143, 113}}},
            {"saf", {{212, 163, 115}}}, {"er", {{178, 58, 72}}},
        };

        animation = std::make_unique<AnimationInterface>(outDir + "/animation.xml");
        animation->SetMaxPktsPerTraceFile(500000);
        for (const auto& spec : scenario.nodes)
        {
            animation->UpdateNodeDescription(nodes[spec.id], spec.id);
            // Nodes are kilometres apart; NetAnim's default size is invisible here.
            animation->UpdateNodeSize(nodes[spec.id], 400.0, 400.0);
            auto colour = colours.find(spec.role);
            if (colour != colours.end())
            {
                animation->UpdateNodeColor(nodes[spec.id],
                                           colour->second[0],
                                           colour->second[1],
                                           colour->second[2]);
            }
        }
    }

    NS_LOG_UNCOND("aisg dual-homed backhaul: " << scenario.nodes.size() << " nodes, "
                                               << scenario.links.size() << " point-to-point links, "
                                               << scenario.sites.size() << " sites, CPE antenna "
                                               << cpeGain << " dBi, " << simTime
                                               << " s simulated");
    Simulator::Stop(Seconds(simTime));
    Simulator::Run();

    monitor->SerializeToXmlFile(outDir + "/flowmon.xml", true, true);
    std::ofstream csv(outDir + "/sites.csv");
    csv << "index,site,primary,scada_sent,scada_received,scada_loss_pct,rtt_mean_ms,rtt_max_ms,"
           "telemetry_sent,telemetry_received,noc_medium_end,er_medium_end\n";
    std::ofstream requests(outDir + "/requests.csv");
    requests << "site,sequence,sent_s,rtt_ms\n";
    for (const auto& site : traffic)
    {
        site->WriteCsvRow(csv);
        site->WriteCsvRow(std::cout);
        site->WriteRequests(requests);
    }
    std::ofstream events(outDir + "/events.csv");
    events << "time_s,subject,event,detail\n";
    for (const auto& event : g_events)
    {
        events << event.time << ',' << event.subject << ',' << event.what << ",\"" << event.detail
               << "\"\n";
        std::cout << "event " << event.time << " s  " << event.subject << "  " << event.what
                  << "  " << event.detail << '\n';
    }
    Simulator::Destroy();
    return 0;
}
