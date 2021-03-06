# Copyright 2012 SINA Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""The instance interfaces extension."""

import webob
from webob import exc

from nova.api.openstack import extensions
from nova import compute
from nova import exception
from nova import network
from nova.openstack.common import log as logging


LOG = logging.getLogger(__name__)
authorize = extensions.extension_authorizer('compute', 'attach_interfaces')


def _translate_interface_attachment_view(port_info):
    """Maps keys for interface attachment details view."""
    return {
        'net_id': port_info['network_id'],
        'port_id': port_info['id'],
        'mac_addr': port_info['mac_address'],
        'port_state': port_info['status'],
        'fixed_ips': port_info.get('fixed_ips', None),
        }


class InterfaceAttachmentController(object):
    """The interface attachment API controller for the OpenStack API."""

    def __init__(self):
        self.compute_api = compute.API()
        self.network_api = network.API()
        super(InterfaceAttachmentController, self).__init__()

    def index(self, req, server_id):
        """Returns the list of interface attachments for a given instance."""
        return self._items(req, server_id,
            entity_maker=_translate_interface_attachment_view)

    def show(self, req, server_id, id):
        """Return data about the given interface attachment."""
        context = req.environ['nova.context']
        authorize(context)

        port_id = id
        try:
            instance = self.compute_api.get(context, server_id)
        except exception.NotFound:
            raise exc.HTTPNotFound()

        try:
            port_info = self.network_api.show_port(context, port_id)
        except exception.NotFound:
            raise exc.HTTPNotFound()

        if port_info['port']['device_id'] != server_id:
            raise exc.HTTPNotFound()

        return {'interfaceAttachment': _translate_interface_attachment_view(
                port_info['port'])}

    def create(self, req, server_id, body):
        """Attach an interface to an instance."""
        context = req.environ['nova.context']
        authorize(context)

        network_id = None
        port_id = None
        req_ip = None
        if body:
            attachment = body['interfaceAttachment']
            network_id = attachment.get('net_id', None)
            port_id = attachment.get('port_id', None)
            try:
                req_ip = attachment['fixed_ips'][0]['ip_address']
            except Exception:
                pass

        if network_id and port_id:
            raise exc.HTTPBadRequest()
        if req_ip and not network_id:
            raise exc.HTTPBadRequest()

        try:
            instance = self.compute_api.get(context, server_id)
            LOG.audit(_("Attach interface"), instance=instance)
            network_info = self.compute_api.attach_interface(context,
                instance, network_id, port_id, req_ip)
        except exception.NotFound as e:
            LOG.exception(e)
            raise exc.HTTPNotFound()
        except NotImplementedError:
            msg = _("Network driver does not support this function.")
            raise webob.exc.HTTPNotImplemented(explanation=msg)
        except exception.InterfaceAttachFailed as e:
            LOG.exception(e)
            msg = _("Failed to attach interface")
            raise webob.exc.HTTPInternalServerError(explanation=msg)

        network, mapping = network_info
        return self.show(req, server_id, mapping['vif_uuid'])

    def update(self, req, server_id, id, body):
        """Update a interface attachment.  We don't currently support this."""
        msg = _("Attachments update is not supported")
        raise exc.HTTPNotImplemented(explanation=msg)

    def delete(self, req, server_id, id):
        """Detach an interface from an instance."""
        context = req.environ['nova.context']
        authorize(context)
        port_id = id

        try:
            instance = self.compute_api.get(context, server_id)
            LOG.audit(_("Detach interface %s"), port_id, instance=instance)

        except exception.NotFound:
            raise exc.HTTPNotFound()
        try:
            self.compute_api.detach_interface(context,
                instance, port_id=port_id)
        except exception.PortNotFound:
            raise exc.HTTPNotFound()
        except NotImplementedError:
            msg = _("Network driver does not support this function.")
            raise webob.exc.HTTPNotImplemented(explanation=msg)

        return webob.Response(status_int=202)

    def _items(self, req, server_id, entity_maker):
        """Returns a list of attachments, transformed through entity_maker."""
        context = req.environ['nova.context']
        authorize(context)

        try:
            instance = self.compute_api.get(context, server_id)
        except exception.NotFound:
            raise exc.HTTPNotFound()

        results = []
        search_opts = {'device_id': instance['uuid']}

        try:
            data = self.network_api.list_ports(context, **search_opts)
        except exception.NotFound:
            raise exc.HTTPNotFound()
        except NotImplementedError:
            msg = _("Network driver does not support this function.")
            raise webob.exc.HTTPNotImplemented(explanation=msg)

        ports = data.get('ports', [])
        results = [entity_maker(port) for port in ports]

        return {'interfaceAttachments': results}


class Attach_interfaces(extensions.ExtensionDescriptor):
    """Attach interface support."""

    name = "AttachInterfaces"
    alias = "os-attach-interfaces"
    namespace = "http://docs.openstack.org/compute/ext/interfaces/api/v1.1"
    updated = "2012-07-22T00:00:00+00:00"

    def get_resources(self):
        resources = []

        res = extensions.ResourceExtension('os-interface',
                                           InterfaceAttachmentController(),
                                           parent=dict(
                                                member_name='server',
                                                collection_name='servers'))
        resources.append(res)

        return resources
