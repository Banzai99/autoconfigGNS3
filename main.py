import gns3fy


if __name__ == '__main__':
    gns3_server = gns3fy.Gns3Connector("http://localhost:3080")
    lab = gns3fy.Project(name = "MerciJean", connector=gns3_server)
    lab.get()

    liens = lab.links
    nodes = lab.nodes
    print(len(liens))

    topologie = {}
    for node in nodes:
        topologie[node.node_id] = {}
    print(topologie)

    for link in liens:
        #print(link)
        for link_side in link.nodes:
            #print(link_side)
            for key in topologie:
                if (key == link_side["node_id"]) and (key == link.nodes[1]["node_id"]):
                    topologie[key][link.nodes[0]["node_id"]] = link_side["label"]["text"]
                elif (key == link_side["node_id"]) and (key == link.nodes[0]["node_id"]):
                    topologie[key][link.nodes[1]["node_id"]] = link_side["label"]["text"]

    print(topologie)

network={}
network_inc=1
inc=1

for key in topologie:
    f=open("config_R"+str(inc)+".txt", "a")

    f.write("""
no ip domain lookup\n
ip arp proxy disable\n""")


    for node in topologie[key]:
        address=0
        exist=False
        try:
            a=network[node][key]
            exist=True
        except:
            pass

        if !exist:
            address=network_inc
            network[key][node]=network_inc+1
            network_inc+=4
        else:
            address=network[node][key]


        f.write(f"""
interface {topologie[key][node]}\n
  no shutdown\n
  ip address 172.30.128.{address} 255.255.255.252\n
    ip ospf 4 area 0\n
    mpls ip\n
exit\n
            """)

    f.write(f"""
router ospf 4\n
  router-id 0.0.0.{inc}\n
  redistribute connected subnets\n
exit\n
mpls ldp discovery targeted-hello  accept\n
ip cef\n
        """)        
    f.close()
    inc++