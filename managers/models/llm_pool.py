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

from config.llm import LLM_PORT_CONFIG, OLLAMA_HOST
from config.podman import LLM_PODMAN_PREFIX, POD_UTIL_THRESHOLD

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
    res_host = OLLAMA_HOST
    try:
        ports_list = LLM_PORT_CONFIG[model] # LLM model-specific ports
    except Exception as e:
        raise Exception(f"{model} port/s not defined in LLM config file.")

    if not isinstance(ports_list, list):
        # If only one port is assigned to LLM
        return (res_host, ports_list)

    res_port = ports_list[0]
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
                    if (n_running_procs < 2) or (c_util < float(POD_UTIL_THRESHOLD)):
                        # Get podman host port details
                        c_port_info = c.inspect()['NetworkSettings']['Ports']['11434/tcp'][0]
                        print(f"{c.name} :: CPRTS :: {c_port_info}")
                        c_port_num = int(c_port_info['HostPort'])
                        c_host = c_port_info['HostIp']
                        if c_port_num in ports_list:
                            print(f"FOUND :: {c.name} :: {c_host} :: {c_port_num}")
                            res_host = c_host
                            res_port = c_port_num
                            return (res_host, res_port)
    except Exception as e:
        print(f"Podman connection failed with error : {str(e)}")
    # Randomly assign if all podmans are loaded
    res_port = int(random.choice(ports_list))
    print(f"NOT FOUND :: Returning ({res_host},{res_port})")
    return (res_host, res_port)