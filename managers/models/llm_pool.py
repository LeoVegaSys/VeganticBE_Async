'''
The purpose of this code is to find a running container 
with no ongoing ollama processes.
The list of ports for a given model provides options to
run the ollama queries in parallel over multiple 
podmans.
'''
import os
import random
from podman import PodmanClient

from config.llm import LLM_PODMAN_PREFIX, LLM_PORT_CONFIG, OLLAMA_HOST

'''
To enable podman.sock for rootless podman execution:
    systemctl --user enable --now podman.socket

Verify socket is active:
    systemctl --user status podman.socket
'''


def get_total_utiln(usage_list: str) -> float:
    return sum(float(item[0]) for item in usage_list)


def get_available_port(model: str):
    '''
    Purpose: To distribute LLM load across multiple podmans
    Running LLM podmans are scanned for running processes
    and utilization. 
    Tasks are assigned to podmans based on existing workload
    '''
    # Rootless podman sock
    base_url=f"unix:///run/user/{os.getuid()}/podman/podman.sock"
    ports_list = LLM_PORT_CONFIG[model] # LLM model-specific ports
    res_host = OLLAMA_HOST
    res_port = ports_list[0]
    found = False
    print(f"MDL :: {model} :: PRTS :: {ports_list}")
    try:
        with PodmanClient(base_url=base_url) as client:
            # Get running podmans
            containers = client.containers.list(filters={"status": "running"})
            print(f"Running containers count :: {len(containers)}")
            for c in containers:
                # Get running LLM podmans
                if c.name.startswith(LLM_PODMAN_PREFIX):
                    # Get number of running podman processes
                    n_running_procs = len(c.top(ps_args=['pcpu'])['Processes'])
                    # Get total utilization of running podman processes
                    c_util = get_total_utiln(c.top(ps_args=['pcpu'])['Processes'])
                    print(f"CNAME :: {c.name} :: PROCS_COUNT :: {n_running_procs} :: UTIL :: {c_util}")
                    if (n_running_procs < 2) or (c_util < 100.0):
                        # Get podman host port details
                        c_port_info = c.inspect()['NetworkSettings']['Ports']['11434/tcp'][0]
                        print(f"{c.name} :: CPRTS :: {c_port_info}")
                        c_port_num = int(c_port_info['HostPort'])
                        c_host = c_port_info['HostIp']
                        if c_port_num in ports_list:
                            found = True
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
        if not found:
            # Randomly assign if all podmans are loaded
            res_port = int(random.choice(ports_list))
        return (res_host, res_port)