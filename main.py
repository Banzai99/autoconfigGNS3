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
        print(link)
        for link_side in link.nodes:
            print(link_side)
            for key in topologie:
                if (key == link_side["node_id"]) and (key == link.nodes[1]["node_id"]):
                    topologie[key][link.nodes[0]["node_id"]] = link_side["label"]["text"]
                elif (key == link_side["node_id"]) and (key == link.nodes[0]["node_id"]):
                    topologie[key][link.nodes[1]["node_id"]] = link_side["label"]["text"]

    print(topologie)
