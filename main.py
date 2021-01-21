import gns3fy
import json
import telnetlib
import time

if __name__ == '__main__':
    gns3_server = gns3fy.Gns3Connector("http://localhost:3080")
    lab = gns3fy.Project(name="testScript", connector=gns3_server)
    lab.get()

    # """----------------prétraitement (création des dictionnaires)----------------"""

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

    for router in backbone: #adresses pour le backbone
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

    for router in edges: #adresses pour les PE (PE-CE)
        incIP = 1
        for node in edges[router]:
            edges[router][node][1] = ipRange + str(subnet) + "." + str(incIP)
            incIP += 1
            network[node] = {}
            network[node][router] = ipRange + str(subnet) + "." + str(incIP)
            incIP += 3
        edges[router]["lb"] = loopBack + str(incLb)
        incLb += 1
        subnet += 1

    for router in custEdges: #adresses pour les CE (PE-CE)
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

        if router in edges: #configuration des interfaces si le routeur est un PE
            f.write(f"""router ospf 4
        router-id 0.0.0.{inc}
        redistribute connected subnets
        network 172.16.1.0 0.0.0.3 area 0
        network 172.30.128.0 0.0.0.255 area 0
        exit
mpls ldp discovery targeted-hello accept
ip cef
exit""") 
        else: #configuration des interfaces si le routeur est un P
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

        for node in custEdges[router]: #configuration des interfaces pour les CE
            f.write(f"""interface {custEdges[router][node][0]}
        no shutdown
        ip address {custEdges[router][node][1]} 255.255.255.252
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
    with open('conf.json') as confFile: #récupère la configuration des vrf
        conf = json.load(confFile)
    for vrf in conf:
        conf[vrf]["id"] = inc #valeurs qui va pouvoir être incrémenté par la suite pour l'attribution des rd
        conf[vrf]["rt"] = 1 #idem pour les rt
        vrfRT[vrf] = [] #clé vrf associée à une liste de rt
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
                if nodeName[node] in conf[vrf]["CE"]: #attribution des rt, rd et des interfaces pour les vrf si un CE d'un PE fait bien parti de la vrf traitée
                    
                    if router in vrfPE: #profite ici de remplir un dictionnaire les vrf qu'un PE contient
                        if vrf not in vrfPE[router]:
                            vrfPE[router].append(vrf)
                    else:
                        vrfPE[router] = []
                        vrfPE[router].append(vrf)

                    RT = conf[vrf]["id"] * 100 + conf[vrf]["rt"]
                    vrfRT[vrf].append(RT) #rajoute dans un dicionnaire pour une vrf d'un CE les exports qu'il utilise
                    f.write(f"""
        ip vrf {vrf}
            rd 1:{RD}
            route-target export 1:{RT}
            exit
        """)
                    f.write(f"""interface {edges[router][node][0]}
                    ip vrf forwarding {vrf}
                    ip address {edges[router][node][1]} 255.255.255.252
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
                    for RT in vrfRT[vrf]: #utilise tous les rt qui ont été utilisé pour l'export ici en import
                        f.write(f"""
        ip vrf {vrf}
            route-target import 1:{RT}
            exit
            """)
        f.close()

    # """-------------------------------------------------------"""

   # """----------------site partagé----------------"""

    shareWebsite = {}
    with open('site_partagé.json') as shareFile:
        shareWebsite = json.load(shareFile)

    rtImp = 1
    for router in custEdges:
        for vrf in shareWebsite:
            if nodeName[router] in list(shareWebsite[vrf].values())[0]: #vérifie que le CE a bien accès au site partagé
                for PE in edges:
                    if router in edges[PE]: #vérifie que le CE est bien connecté au PE
                        for vrfCE in conf:
                            if nodeName[router] in conf[vrfCE]["CE"]: #rajoute les import/export nécessaire pour communiquer avec le site partagé dans la bonne vrf
                                if len(vrfRT[vrf]) == 1: #si l'export du site partagé n'a pas encore été crée, on le crée
                                    vrfRT[vrf].append(rtImp)
                                    rtImp += 1
                                f = open("config_" + nodeName[PE] + ".txt", "a")
                                print(nodeName[PE])
                                f.write(f"""
                    ip vrf {vrfCE}
                        route-target import 1:{vrfRT[vrf][0]}
                        route-target export 1:{vrfRT[vrf][1]}
                        exit
                        """)
                                f.close()

    for router in edges:
        for node in edges[router]:
            for vrf in shareWebsite:
                if node == "lb":
                    continue
                if nodeName[node] in shareWebsite[vrf]: #rajoute l'import du site partagé dans le bon CE
                    f = open("config_" + nodeName[router] + ".txt", "a")
                    print(nodeName[router])
                    f.write(f"""
        ip vrf {vrf}
            route-target import 1:{vrfRT[vrf][1]}
            exit
            """)
                    f.close()

    # """-------------------------------------------------------"""

    # """----------------protocole CE-PE----------------"""
    for router in custEdges:
        f = open("config_" + nodeName[router] + ".txt", "a")
        for vrf in conf:
            if nodeName[router] in conf[vrf]["CE"]: #crée un groupe eigrp pour chaque CE
                f.write(f"""
                router eigrp 1
                    network 10.0.0.0
                    no auto-summary
                    exit
                """)  
        f.close()

    for router in edges:
        f = open("config_" + nodeName[router] + ".txt", "a")
        for vrf in vrfPE[router]: #pour chaque vrf d'un PE, on l'associe à un groupe eigrp
            f.write(f"""
                router eigrp 1
                    address-family ipv4 vrf {vrf} autonomous-system 1
                        network 10.0.0.0
                        no auto-summary
                    exit
                """)
        f.close()

    # """-------------------------------------------------------"""

    # """----------------protocole MP-BGP----------------"""

    for router in edges:
        f = open("config_" + nodeName[router] + ".txt", "a")
        for neighbor in edges:
            if neighbor != router: #pour tous les voisins PE d'un PE, on instancie une communication BGP
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
        f.close()

    # """-------------------------------------------------------"""

    # """----------------redistribution respective des préfixes (EIGRP -> BGP + BGP -> EIGRP)----------------"""

    print(vrfPE)
    for router in vrfPE:
        f = open("config_" + nodeName[router] + ".txt", "a")
        for vrf in vrfPE[router]: #pour chaque vrf d'un PE, on l'associe à la redistribution BGP
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
        for vrf in vrfPE[router]: #pour chaque vrf d'un PE, on l'associe à la redistribution eigrp
            f.write(f"""
            router eigrp 1
                address-family ipv4 vrf {vrf}
                    redistribute bgp 1 metric 1024 1 255 1 1500
                    exit
                exit
            """)
        f.close()

    # """-------------------------------------------------------"""

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