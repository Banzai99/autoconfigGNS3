import gns3fy
import json
import telnetlib
import time

if __name__ == '__main__':
    gns3_server = gns3fy.Gns3Connector("http://localhost:3080")
    lab = gns3fy.Project(name="testScript", connector=gns3_server)
    lab.get()

    # """----------------prétraitement----------------"""

    liens = lab.links
    nodes = lab.nodes

    backbone = {}
    edges = {}
    custEdges = {}
    nodeName = {}

    for node in nodes:
        nodeName[node.node_id] = node.name
        if node.name[0:2] == "PE":
            edges[node.node_id] = {}
        if node.name[0] == "P":
            backbone[node.node_id] = {}
            continue
        if node.name.split("_")[1][0:2] == "CE":
            custEdges[node.node_id] = {}
    for link in liens:
        for link_side in link.nodes:
            for router in backbone:
                if (router == link_side["node_id"]) and (router == link.nodes[1]["node_id"]) and (
                        link.nodes[0]["node_id"] in backbone.keys()):
                    backbone[router][link.nodes[0]["node_id"]] = [link_side["label"]["text"], ""]
                elif (router == link_side["node_id"]) and (router == link.nodes[0]["node_id"]) and (
                        link.nodes[1]["node_id"] in backbone.keys()):
                    backbone[router][link.nodes[1]["node_id"]] = [link_side["label"]["text"], ""]
            for router in edges:
                if (router == link_side["node_id"]) and (router == link.nodes[1]["node_id"]) and not (
                        link.nodes[0]["node_id"] in backbone.keys()):
                    edges[router][link.nodes[0]["node_id"]] = [link_side["label"]["text"], ""]
                elif (router == link_side["node_id"]) and (router == link.nodes[0]["node_id"]) and not (
                        link.nodes[1]["node_id"] in backbone.keys()):
                    edges[router][link.nodes[1]["node_id"]] = [link_side["label"]["text"], ""]
            for router in custEdges:
                if (router == link_side["node_id"]) and (router == link.nodes[1]["node_id"]):
                    custEdges[router][link.nodes[0]["node_id"]] = [link_side["label"]["text"], ""]
                elif (router == link_side["node_id"]) and (router == link.nodes[0]["node_id"]):
                    custEdges[router][link.nodes[1]["node_id"]] = [link_side["label"]["text"], ""]
    # """-------------------------------------------------------"""

    # """----------------attribution des adresses IP----------------"""

    network = {}
    ipRange = "172.30.128."
    networkInc = 1

    for router in backbone:
        for node in backbone[router]:
            if router in network:
                if node in network[router]:
                    backbone[router][node][1] = network[router][node]
                    continue
            backbone[router][node][1] = ipRange + str(networkInc)
            network[node] = {}
            network[node][router] = ipRange + str(networkInc + 1)
            networkInc += 4

    network = {}
    ipRange = "10.1."
    subnet = 1
    loopBack = "172.16.1."
    incLb = 1

    for router in edges:
        incIP = 2
        for node in edges[router]:
            edges[router][node][1] = ipRange + str(subnet) + "." + str(incIP)
            network[node] = {}
            network[node][router] = ipRange + str(subnet) + ".1"
            incIP += 1
        edges[router]["lb"] = loopBack + str(incLb)
        incLb += 1
        subnet += 1

    for router in custEdges:
        for node in custEdges[router]:
            custEdges[router][node][1] = network[router][node]

    inc = 1
    print(backbone)
    for router in backbone:
        f = open("config_" + nodeName[router] + ".txt", "w")
        f.write(f"""configure terminal
        no ip domain lookup
        ip arp proxy disable
        """)

        for node in backbone[router]:
            f.write(f"""interface {backbone[router][node][0]}
        no shutdown
        ip address {backbone[router][node][1]} 255.255.255.252
                ip ospf 4 area 0
                mpls ip
                exit
        """)

        if router in edges:
            f.write(f"""router ospf 4
        router-id 0.0.0.{inc}
        redistribute connected subnets
        network 172.16.1.0 0.0.0.3 area 0
        network 172.30.128.0 0.0.0.255 area 0
        exit
mpls ldp discovery targeted-hello accept
ip cef
exit""")
        else:
            f.write(f"""router ospf 4
            router-id 0.0.0.{inc}
            redistribute connected subnets
            network 172.30.128.0 0.0.0.255 area 0
            exit
mpls ldp discovery targeted-hello accept
ip cef
exit""")
        f.close()
        inc += 1

    for router in custEdges:
        f = open("config_" + nodeName[router] + ".txt", "w")
        f.write(f"""configure terminal
        no ip domain lookup
        ip arp proxy disable
        """)

        for node in custEdges[router]:
            f.write(f"""interface {custEdges[router][node][0]}
        no shutdown
        ip address {custEdges[router][node][1]} 255.255.255.248
                exit
        """)

        f.write(f"""
ip cef""")

    # """-------------------------------------------------------"""

    # """----------------attribution et configuration des VRF----------------"""

    vrfRT = {}
    inc = 1
    vrfPE = {}

    conf = {}
    with open('conf.json') as confFile:
        conf = json.load(confFile)
    for vrf in conf:
        conf[vrf]["id"] = inc
        conf[vrf]["rt"] = 1
        vrfRT[vrf] = []
        inc += 1

    for router in edges:
        f = open("config_" + nodeName[router] + ".txt", "a")
        f.write(f"""
configure terminal
        interface Lo0
                no shutdown
                ip address {edges[router]['lb']} 255.255.255.255
                exit""")
        RD = 1
        for node in edges[router]:
            if node == "lb":
                continue
            for vrf in conf:
                if nodeName[node] in conf[vrf]["CE"]:
                    if router in vrfPE:
                        if vrf not in vrfPE[router]:
                            vrfPE[router].append(vrf)
                    else:
                        vrfPE[router] = []
                        vrfPE[router].append(vrf)

                    RT = conf[vrf]["id"] * 100 + conf[vrf]["rt"]
                    vrfRT[vrf].append(RT)
                    f.write(f"""
        ip vrf {vrf}
            rd 1:{RD}
            route-target export 1:{RT}
            exit
        """)
                    f.write(f"""interface {edges[router][node][0]}
                    ip vrf forwarding {vrf}
                    ip address {edges[router][node][1]} 255.255.255.248
                    no shutdown
                    exit
                    """)
                    RD += 1
                    conf[vrf]["rt"] += 1

        f.close()

    for router in edges:
        f = open("config_" + nodeName[router] + ".txt", "a")
        for node in edges[router]:
            if node == "lb":
                continue
            for vrf in conf:
                if nodeName[node] in conf[vrf]["CE"]:
                    for RT in vrfRT[vrf]:
                        f.write(f"""
        ip vrf {vrf}
            route-target import 1:{RT}
            exit
            """)
        f.close()

    # """-------------------------------------------------------"""

    # """----------------protocole CE-PE----------------"""
    for router in custEdges:
        f = open("config_" + nodeName[router] + ".txt", "a")
        for vrf in conf:
            if nodeName[router] in conf[vrf]["CE"]:
                f.write(f"""
                router eigrp 1
                    network 10.0.0.0
                    no auto-summary
                    exit
                """)  # rajouter automatisation des network ?
        f.close()

    for router in edges:
        f = open("config_" + nodeName[router] + ".txt", "a")
        for vrf in vrfPE[router]:
            f.write(f"""
                router eigrp 1
                    address-family ipv4 vrf {vrf} autonomous-system 1
                        no auto-summary
                    exit
                """)
    f.close()

    # """-------------------------------------------------------"""

    # """----------------protocole MP-BGP----------------"""

    for router in edges:
        f = open("config_" + nodeName[router] + ".txt", "a")
        for neighbor in edges:
            if neighbor != router:
                f.write(f"""
                router bgp 1
                    neighbor {edges[neighbor]["lb"]} remote-as 1
                    neighbor {edges[neighbor]["lb"]} update-source Lo0
                    address-family vpnv4
                        neighbor {edges[neighbor]["lb"]} activate
                        neighbor {edges[neighbor]["lb"]} send-community extended
                        exit
                    exit
                """)

    # """-------------------------------------------------------"""

    # """----------------redistribution respective des préfixes (EIGRP -> BGP + BGP -> EIGRP)----------------"""

    print(vrfPE)
    for router in vrfPE:
        f = open("config_" + nodeName[router] + ".txt", "a")
        for vrf in vrfPE[router]:
            f.write(f"""
            router bgp 1
                address-family ipv4 vrf {vrf}
                    redistribute eigrp 1 metric 1
                    exit
                exit
                """)
    f.close()

    for router in vrfPE:
        f = open("config_" + nodeName[router] + ".txt", "a")
        for vrf in vrfPE[router]:
            f.write(f"""
            router eigrp 1
                address-family ipv4 vrf {vrf}
                    redistribute bgp 1 metric 1024 1 255 1 1500
                    exit
                exit
            """)

    print(backbone)
    for node in nodes:
        f = open("config_"+nodeName[node.node_id] + ".txt", "r")
        port = node.console
        command = f.readline()
        with telnetlib.Telnet('localhost', port) as tn:
            tn.write(b"\r\n")
            time.sleep(1)
            while command:
                time.sleep(0.1)
                tn.write(command.encode("ascii"))
                tn.write(b"\r\n")
                command = f.readline()
            tn.write(b"exit")
            tn.write(b"\r\n")