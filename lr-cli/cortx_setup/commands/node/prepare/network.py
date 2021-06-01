#
# Copyright (c) 2020 Seagate Technology LLC and/or its Affiliates
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
# For any questions about this software or licensing,
# please email opensource@seagate.com or cortx-questions@seagate.com.
#

# Cortx Setup API for Preparing network in field

from cortx_setup.commands.command import Command
from cortx_setup.config import CONFSTORE_CLUSTER_FILE
from cortx_setup.commands.common_utils import get_machine_id
from provisioner import (
    set_hostname,
    set_mgmt_network,
    set_public_data_network,
    set_private_data_network
)
from provisioner.salt import local_minion_id
from cortx.utils.conf_store import Conf


class NodePrepareNetwork(Command):
    _args = {
        'hostname': {
            'type': str,
            'optional': True,
            'default': None,
            'help': 'Hostname to be set'
        },
        'type': {
            'type': str,
            'optional': True,
            'default': None,
            'dest': 'network_type',
            'choices': ['data', 'private', 'management'],
            'help': 'Type of network to prepare'
        },
        'gateway': {
            'type': str,
            'optional': True,
            'default': "",
            'help': 'Gateway IP'
        },
        'netmask': {
            'type': str,
            'optional': True,
            'default': "",
            'help': 'Netmask'
        },
        'ip_address': {
            'type': str,
            'optional': True,
            'default': "",
            'help': 'IP address'
        },
        'interfaces': {
            'type': str,
            'nargs': '+',
            'optional': True,
            'default': "",
            'help': 'List of interfaces e.g eth1 eth2'
        }
    }

    def update_network_confstore(self, network_type, key, value, target):

        """
        Set network parameters in confstore
        Parameters
        ----------
        network_type: str
            Type of network
        key: str
            Confstore key to update
        value: str
            Value to set
        target: str
            Node id
        """

        machine_id = get_machine_id(target)
        if value:
            self.logger.debug(
                f"Set {network_type} network {key} to {value}"
            )
            if network_type == 'private':
                network_type = 'data'
            Conf.set(
                'node_prepare_index',
                f'server_node>{machine_id}>network>{network_type}>{key}',
                value
            )

    def run(self, hostname=None, network_type=None, gateway=None, netmask=None,
        ip_address=None, interfaces=None
    ):

        """Network prepare execution method.

        Execution:
        `cortx_setup node prepare network --hostname <hostname>`
        `cortx_setup node prepare network --type <type> --ip_address <ip_address>
                --interfaces <iface1> --netmask <netmask> --gateway <gateway>`
        `cortx_setup node prepare network --type data --ip_address <ip_address>
                --interfaces <iface1 iface2> --netmask <netmask> --gateway <gateway>`
        `cortx_setup node prepare network --type private --ip_address <ip_address>
                --interfaces <iface1 iface2> --netmask <netmask> --gateway <gateway>`

        """

        node_id = local_minion_id()
        machine_id = get_machine_id(node_id)
        Conf.load(
            'node_prepare_index',
            f'json://{CONFSTORE_CLUSTER_FILE}'
        )

        if hostname is not None:
            self.logger.debug(f"Setting up system hostname to {hostname}")
            try:
                set_hostname(hostname=hostname, targets=node_id, local=True)
                Conf.set(
                    'node_prepare_index',
                    f'server_node>{machine_id}>hostname',
                    hostname
                )
            except Exception as ex:
                raise ex

        if network_type is not None:

            if interfaces is None:
                raise Exception("Interfaces should be provided")

            config_method = 'Static' if ip_address else 'DHCP'
            self.logger.debug(
                f"Configuring {network_type} network using {config_method} method"
            )

            try:
                if network_type == 'management':
                    iface_key = 'interfaces'
                    set_mgmt_network(
                        mgmt_public_ip=ip_address,
                        mgmt_netmask=netmask,
                        mgmt_gateway=gateway,
                        mgmt_interfaces=interfaces,
                        local=True,
                        targets=node_id
                    )
                elif network_type == 'data':
                    iface_key = 'public_interfaces'
                    set_public_data_network(
                        data_public_ip=ip_address,
                        data_netmask=netmask,
                        data_gateway=gateway,
                        data_public_interfaces=interfaces,
                        local=True,
                        targets=node_id
                    )
                elif network_type == 'private':
                    iface_key = 'private_interfaces'
                    set_private_data_network(
                        data_private_ip=ip_address,
                        data_private_interfaces=interfaces,
                        local=True,
                        targets=node_id
                    )
            except Exception as ex:
                raise ex

            self.update_network_confstore(
                network_type=network_type, key=iface_key, value=interfaces, target=node_id
            )
            if config_method == 'Static':
                self.update_network_confstore(
                    network_type=network_type,
                    key='private_ip' if network_type == 'private' else 'public_ip',
                    value=ip_address, target=node_id
                )
                self.update_network_confstore(
                    network_type=network_type, key='netmask', value=netmask, target=node_id
                )
                self.update_network_confstore(
                    network_type=network_type, key='gateway', value=gateway, target=node_id
                )

        Conf.save('node_prepare_index')
        self.logger.debug("Done")
