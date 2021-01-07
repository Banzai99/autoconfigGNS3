import gns3fy


if __name__ == '__main__':
    gns3_server = gns3fy.Gns3Connector("http://localhost:3080")
    lab = gns3fy.Project(name = "tpmplsvpn", connector=gns3_server)
    lab.get()

    liens = lab.links
    nodes = lab.nodes
    print(len(liens))

    backbone = {}
    edges = {}
    custEdges = {}
    for node in nodes:
        if node.name[0:2] == "PE":
            edges[node.node_id] = {}
        if node.name[0] == "P":
            backbone[node.node_id] = {}
            continue
        if node.name.split("_")[1][0:2] == "CE":
            custEdges[node.node_id] = {}
    print(backbone)
    print(edges)
    print(custEdges)
    for link in liens:
        #print(link)
        print(link.capture_file_name)
        for link_side in link.nodes:
            for router in backbone:
                if (router == link_side["node_id"]) and (router == link.nodes[1]["node_id"]) and (link.nodes[0]["node_id"] in backbone.keys()):
                    backbone[router][link.nodes[0]["node_id"]] = link_side["label"]["text"]
                elif (router == link_side["node_id"]) and (router == link.nodes[0]["node_id"]) and (link.nodes[1]["node_id"] in backbone.keys()):
                    backbone[router][link.nodes[1]["node_id"]] = link_side["label"]["text"]
            for router in edges:
                if (router == link_side["node_id"]) and (router == link.nodes[1]["node_id"]) and not (link.nodes[0]["node_id"] in backbone.keys()):
                    edges[router][link.nodes[0]["node_id"]] = link_side["label"]["text"]
                elif (router == link_side["node_id"]) and (router == link.nodes[0]["node_id"]) and not (link.nodes[1]["node_id"] in backbone.keys()):
                    edges[router][link.nodes[1]["node_id"]] = link_side["label"]["text"]
            for router in custEdges:
                if (router == link_side["node_id"]) and (router == link.nodes[1]["node_id"]):
                    custEdges[router][link.nodes[0]["node_id"]] = link_side["label"]["text"]
                elif (router == link_side["node_id"]) and (router == link.nodes[0]["node_id"]):
                    custEdges[router][link.nodes[1]["node_id"]] = link_side["label"]["text"]

    network={}
    network_inc=1
    inc=1
    for router in backbone:
        print("topo key", backbone[router])
        f=open("config_R"+str(inc)+".txt", "w")
        network[router] = {}
        f.write("""configure terminal\n
        no ip domain lookup\n
        ip arp proxy disable\n""")
        for node in backbone[router]:
            address = 0
            exist = False
            try:
                a = network[node][router]
                exist = True
            except:
                pass
            if not exist:
                address = network_inc
                network[router][node] = network_inc + 1
                print("network ",network)
                network_inc += 4
            else:
                address = network[node][router]
            f.write(f"""interface {backbone[router][node]}
            no shutdown
            ip address 172.30.128.{address} 255.255.255.252
            ip ospf 4 area 0
            mpls ip
            exit\n""")

        f.write(f"""router ospf 4
        router-id 0.0.0.{inc}
        redistribute connected subnets
        exit
        mpls ldp discovery targeted-hello  accept
        ip cef
        exit""")
        f.close()
        inc += 1
