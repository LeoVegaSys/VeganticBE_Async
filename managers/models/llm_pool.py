'''
The purpose of this code is to find a running container 
with no ongoing ollama processes.
The list of ports for a given model provides options to
run the ollama queries in parallel over multiple 
podmans.
'''
import os
from podman import PodmanClient

from config.llm import LLM_PODMAN_PREFIX, LLM_PORT_CONFIG, OLLAMA_HOST

'''
To enable podman.sock for rootless podman execution:
    systemctl --user enable --now podman.socket

Verify socket is active:
    systemctl --user status podman.socket
'''


def get_available_port(model: str) :
    base_url=f"unix:///run/user/{os.getuid()}/podman/podman.sock"
    ports_list = LLM_PORT_CONFIG[model]
    res_host = OLLAMA_HOST
    res_port = ports_list[0]

    print(f"MDL :: {model} :: PRTS :: {ports_list}")
    try:
        with PodmanClient(base_url=base_url) as client:
            containers = client.containers.list(filters={"status": "running"})
            print(f"Running containers count :: {len(containers)}")
            for c in containers:
                if c.name.startswith(LLM_PODMAN_PREFIX):
                    n_running_procs = len(c.top()['Processes'])
                    print(f"CNAME :: {c.name} :: PROCS_COUNT :: {n_running_procs}")
                    if n_running_procs < 2:
                        c_port_info = c.inspect()['NetworkSettings']['Ports']['11434/tcp'][0]
                        print(f"{c.name} :: CPRTS :: {c_port_info}")
                        c_port_num = int(c_port_info['HostPort'])
                        c_host = c_port_info['HostIp']
                        if c_port_num in ports_list:
                            print(f"FOUND :: {c.name} :: {c_host} :: {c_port_num}")
                            res_host = c_host
                            res_port = c_port_num
                            break
                    else:
                        continue
    except Exception as e:
        print(f"Podman connection failed with error : {str(e)}")
    finally:
        print(f"Returning ({res_host},{res_port})")
        return (res_host, res_port)