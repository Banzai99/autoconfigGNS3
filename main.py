import gns3fy
import json

if __name__ == '__main__':
    gns3_server = gns3fy.Gns3Connector("http://localhost:3080")
    lab = gns3fy.Project(name="tpmplsvpn", connector=gns3_server)
    lab.get()

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
        for node in edges[router]:
            edges[router][node][1] = ipRange + str(subnet) + ".2"
            network[node] = {}
            network[node][router] = ipRange + str(subnet) + ".1"
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

        f.write(f"""router ospf 4
        router-id 0.0.0.{inc}
        redistribute connected subnets
        exit
mpls ldp discovery targeted-hello accept
ip cef
exit""")

        f.close()
        inc += 1

    vrfRT = {}
    inc = 1

    conf = {}
    with open('conf.json') as confFile:
    	conf = json.load(confFile)
    for vrf in conf:
    	conf[vrf]["id"] = inc*100
    	conf[vrf]["rt"] = 1
    	vrfRT[vrf] = []
    	inc += 1


    for router in edges:
        f = open("config_" + nodeName[router] + ".txt", "a")
        f.write(f"""
configure terminal
        interface lo/0
                no shutdown
                ip address {edges[router]['lb']} 255.255.255.255
                exit""")

        for node in edges[router]:
        	RD = 1
        	for vrf in conf:
        		if node in conf[vrf]["CE"]:
        			RT = conf[vrf]["id"]+conf[vrf]["rt"]
        			vrfRT[vrf].append(RT)
		        	f.write(f"""
        		ip vrf {vrf}
        		rd 1:{RD}
        		route export 1:{RT}
        		exit
        		""")
					RD += 1
					conf[vrf]["rt"] += 1
		f.close()

	for router in edges:
		f = open("config_" + nodeName[router] + ".txt", "a")
		for node in edges[router]:
			for vrf in conf:
				if node in conf[vrf]["CE"]:
					for RT in vrfRT[vrf]:
						f.write(f"""
							ip vrf {vrf}
							route import 1:{RT}
							exit
						""")
        f.close()

