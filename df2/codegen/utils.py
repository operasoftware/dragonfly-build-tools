import os

def get_proto_files(src="."):
    protos = []
    for root, dirs, files in os.walk(src):
        absroot = os.path.abspath(root)
        for name in files:
            if name.endswith(".proto"):
                protos.append(os.path.join(root, name))
    return protos
