#    Copyright 2013 IBM Corp.
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

import datetime
import iso8601
import netaddr

from nova import context
from nova import db
from nova.objects import base
from nova.objects import instance
from nova.openstack.common import timeutils
from nova.tests.api.openstack import fakes
from nova.tests.objects import test_objects


class _TestInstanceObject(object):
    @property
    def fake_instance(self):
        fake_instance = fakes.stub_instance(id=2,
                                            access_ipv4='1.2.3.4',
                                            access_ipv6='::1')
        fake_instance['scheduled_at'] = None
        fake_instance['terminated_at'] = None
        fake_instance['deleted_at'] = None
        fake_instance['created_at'] = None
        fake_instance['updated_at'] = None
        fake_instance['launched_at'] = (
            fake_instance['launched_at'].replace(
                tzinfo=iso8601.iso8601.Utc(), microsecond=0))
        fake_instance['deleted'] = False
        fake_instance['info_cache']['instance_uuid'] = fake_instance['uuid']
        return fake_instance

    def test_datetime_deserialization(self):
        red_letter_date = timeutils.parse_isotime(
            timeutils.isotime(datetime.datetime(1955, 11, 5)))
        inst = instance.Instance()
        inst.uuid = 'fake-uuid'
        inst.launched_at = red_letter_date
        primitive = inst.obj_to_primitive()
        expected = {'nova_object.name': 'Instance',
                    'nova_object.namespace': 'nova',
                    'nova_object.version': '1.0',
                    'nova_object.data':
                        {'uuid': 'fake-uuid',
                         'launched_at': '1955-11-05T00:00:00Z'},
                    'nova_object.changes': ['uuid', 'launched_at']}
        self.assertEqual(primitive, expected)
        inst2 = instance.Instance.obj_from_primitive(primitive)
        self.assertTrue(isinstance(inst2.launched_at,
                        datetime.datetime))
        self.assertEqual(inst2.launched_at, red_letter_date)

    def test_ip_deserialization(self):
        inst = instance.Instance()
        inst.uuid = 'fake-uuid'
        inst.access_ip_v4 = '1.2.3.4'
        inst.access_ip_v6 = '::1'
        primitive = inst.obj_to_primitive()
        expected = {'nova_object.name': 'Instance',
                    'nova_object.namespace': 'nova',
                    'nova_object.version': '1.0',
                    'nova_object.data':
                        {'uuid': 'fake-uuid',
                         'access_ip_v4': '1.2.3.4',
                         'access_ip_v6': '::1'},
                    'nova_object.changes': ['uuid', 'access_ip_v6',
                                            'access_ip_v4']}
        self.assertEqual(primitive, expected)
        inst2 = instance.Instance.obj_from_primitive(primitive)
        self.assertTrue(isinstance(inst2.access_ip_v4, netaddr.IPAddress))
        self.assertTrue(isinstance(inst2.access_ip_v6, netaddr.IPAddress))
        self.assertEqual(inst2.access_ip_v4, netaddr.IPAddress('1.2.3.4'))
        self.assertEqual(inst2.access_ip_v6, netaddr.IPAddress('::1'))

    def test_get_without_expected(self):
        ctxt = context.get_admin_context()
        self.mox.StubOutWithMock(db, 'instance_get_by_uuid')
        db.instance_get_by_uuid(ctxt, 'uuid', []).AndReturn(self.fake_instance)
        self.mox.ReplayAll()
        inst = instance.Instance.get_by_uuid(ctxt, uuid='uuid')
        # Make sure these weren't loaded
        for attr in instance.INSTANCE_OPTIONAL_FIELDS:
            attrname = base.get_attrname(attr)
            self.assertFalse(hasattr(inst, attrname))
        self.assertRemotes()

    def test_get_with_expected(self):
        ctxt = context.get_admin_context()
        self.mox.StubOutWithMock(db, 'instance_get_by_uuid')
        db.instance_get_by_uuid(
            ctxt, 'uuid',
            instance.INSTANCE_OPTIONAL_FIELDS).AndReturn(self.fake_instance)
        self.mox.ReplayAll()
        inst = instance.Instance.get_by_uuid(
            ctxt, 'uuid', expected_attrs=instance.INSTANCE_OPTIONAL_FIELDS)
        for attr in instance.INSTANCE_OPTIONAL_FIELDS:
            attrname = base.get_attrname(attr)
            self.assertTrue(hasattr(inst, attrname))
        self.assertRemotes()

    def test_load(self):
        ctxt = context.get_admin_context()
        self.mox.StubOutWithMock(db, 'instance_get_by_uuid')
        fake_uuid = self.fake_instance['uuid']
        db.instance_get_by_uuid(ctxt, fake_uuid, []).AndReturn(
            self.fake_instance)
        fake_inst2 = dict(self.fake_instance,
                          system_metadata=[{'key': 'foo', 'value': 'bar'}])
        db.instance_get_by_uuid(ctxt, fake_uuid, ['system_metadata']
                                ).AndReturn(fake_inst2)
        self.mox.ReplayAll()
        inst = instance.Instance.get_by_uuid(ctxt, fake_uuid)
        self.assertFalse(hasattr(inst, '_system_metadata'))
        sys_meta = inst.system_metadata
        self.assertEqual(sys_meta, {'foo': 'bar'})
        self.assertTrue(hasattr(inst, '_system_metadata'))
        # Make sure we don't run load again
        sys_meta2 = inst.system_metadata
        self.assertEqual(sys_meta2, {'foo': 'bar'})
        self.assertRemotes()

    def test_get_remote(self):
        # isotime doesn't have microseconds and is always UTC
        ctxt = context.get_admin_context()
        self.mox.StubOutWithMock(db, 'instance_get_by_uuid')
        fake_instance = self.fake_instance
        db.instance_get_by_uuid(ctxt, 'fake-uuid', []).AndReturn(
            fake_instance)
        self.mox.ReplayAll()
        inst = instance.Instance.get_by_uuid(ctxt, 'fake-uuid')
        self.assertEqual(inst.id, fake_instance['id'])
        self.assertEqual(inst.launched_at, fake_instance['launched_at'])
        self.assertEqual(str(inst.access_ip_v4),
                         fake_instance['access_ip_v4'])
        self.assertEqual(str(inst.access_ip_v6),
                         fake_instance['access_ip_v6'])
        self.assertRemotes()

    def test_refresh(self):
        ctxt = context.get_admin_context()
        self.mox.StubOutWithMock(db, 'instance_get_by_uuid')
        fake_uuid = self.fake_instance['uuid']
        db.instance_get_by_uuid(ctxt, fake_uuid, []).AndReturn(
            dict(self.fake_instance, host='orig-host'))
        db.instance_get_by_uuid(ctxt, fake_uuid, []).AndReturn(
            dict(self.fake_instance, host='new-host'))
        self.mox.ReplayAll()
        inst = instance.Instance.get_by_uuid(ctxt, fake_uuid)
        self.assertEqual(inst.host, 'orig-host')
        inst.refresh()
        self.assertEqual(inst.host, 'new-host')
        self.assertRemotes()

    def test_save(self):
        ctxt = context.get_admin_context()
        fake_inst = dict(self.fake_instance, host='oldhost')
        fake_uuid = fake_inst['uuid']
        self.mox.StubOutWithMock(db, 'instance_get_by_uuid')
        self.mox.StubOutWithMock(db, 'instance_update_and_get_original')
        self.mox.StubOutWithMock(db, 'instance_info_cache_update')
        db.instance_get_by_uuid(ctxt, fake_uuid, []).AndReturn(fake_inst)
        db.instance_update_and_get_original(
            ctxt, fake_uuid, {'user_data': 'foo'}).AndReturn(
                (fake_inst, dict(fake_inst, host='newhost')))
        self.mox.ReplayAll()
        inst = instance.Instance.get_by_uuid(ctxt, fake_uuid)
        inst.user_data = 'foo'
        inst.save()
        self.assertEqual(inst.host, 'newhost')

    def test_get_deleted(self):
        ctxt = context.get_admin_context()
        fake_inst = dict(self.fake_instance, id=123, deleted=123)
        fake_uuid = fake_inst['uuid']
        self.mox.StubOutWithMock(db, 'instance_get_by_uuid')
        db.instance_get_by_uuid(ctxt, fake_uuid, []).AndReturn(fake_inst)
        self.mox.ReplayAll()
        inst = instance.Instance.get_by_uuid(ctxt, fake_uuid)
        # NOTE(danms): Make sure it's actually a bool
        self.assertEqual(inst.deleted, True)

    def test_with_info_cache(self):
        ctxt = context.get_admin_context()
        fake_inst = dict(self.fake_instance)
        fake_uuid = fake_inst['uuid']
        fake_inst['info_cache'] = {'network_info': 'foo',
                                   'instance_uuid': fake_uuid}
        self.mox.StubOutWithMock(db, 'instance_get_by_uuid')
        self.mox.StubOutWithMock(db, 'instance_update_and_get_original')
        self.mox.StubOutWithMock(db, 'instance_info_cache_update')
        db.instance_get_by_uuid(ctxt, fake_uuid, []).AndReturn(fake_inst)
        db.instance_info_cache_update(ctxt, fake_uuid,
                                      {'network_info': 'bar'})
        self.mox.ReplayAll()
        inst = instance.Instance.get_by_uuid(ctxt, fake_uuid)
        self.assertEqual(inst.info_cache.network_info,
                         fake_inst['info_cache']['network_info'])
        self.assertEqual(inst.info_cache.instance_uuid, fake_uuid)
        inst.info_cache.network_info = 'bar'
        inst.save()


class TestInstanceObject(test_objects._LocalTest,
                         _TestInstanceObject):
    pass


class TestRemoteInstanceObject(test_objects._RemoteTest,
                               _TestInstanceObject):
    pass


class _TestInstanceListObject(object):
    def fake_instance(self, id, updates=None):
        fake_instance = fakes.stub_instance(id=2,
                                            access_ipv4='1.2.3.4',
                                            access_ipv6='::1')
        fake_instance['scheduled_at'] = None
        fake_instance['terminated_at'] = None
        fake_instance['deleted_at'] = None
        fake_instance['created_at'] = None
        fake_instance['updated_at'] = None
        fake_instance['launched_at'] = (
            fake_instance['launched_at'].replace(
                tzinfo=iso8601.iso8601.Utc(), microsecond=0))
        fake_instance['info_cache'] = {'network_info': 'foo',
                                       'instance_uuid': fake_instance['uuid']}
        fake_instance['deleted'] = 0
        if updates:
            fake_instance.update(updates)
        return fake_instance

    def test_get_all_by_filters(self):
        fakes = [self.fake_instance(1), self.fake_instance(2)]
        ctxt = context.get_admin_context()
        self.mox.StubOutWithMock(db, 'instance_get_all_by_filters')
        db.instance_get_all_by_filters(ctxt, {'foo': 'bar'}, 'uuid', 'asc',
                                       None, None,
                                       columns_to_join=['metadata']).AndReturn(
                                           fakes)
        self.mox.ReplayAll()
        inst_list = instance.InstanceList.get_by_filters(
            ctxt, {'foo': 'bar'}, 'uuid', 'asc', expected_attrs=['metadata'])

        for i in range(0, len(fakes)):
            self.assertTrue(isinstance(inst_list.objects[i],
                                       instance.Instance))
            self.assertEqual(inst_list.objects[i].uuid, fakes[i]['uuid'])
        self.assertRemotes()

    def test_get_by_host(self):
        fakes = [self.fake_instance(1),
                 self.fake_instance(2)]
        ctxt = context.get_admin_context()
        self.mox.StubOutWithMock(db, 'instance_get_all_by_host')
        db.instance_get_all_by_host(ctxt, 'foo',
                                    columns_to_join=None).AndReturn(fakes)
        self.mox.ReplayAll()
        inst_list = instance.InstanceList.get_by_host(ctxt, 'foo')
        for i in range(0, len(fakes)):
            self.assertTrue(isinstance(inst_list.objects[i],
                                       instance.Instance))
            self.assertEqual(inst_list.objects[i].uuid, fakes[i]['uuid'])
        self.assertEqual(inst_list.obj_what_changed(), set())
        self.assertRemotes()

    def test_get_by_host_and_node(self):
        fakes = [self.fake_instance(1),
                 self.fake_instance(2)]
        ctxt = context.get_admin_context()
        self.mox.StubOutWithMock(db, 'instance_get_all_by_host_and_node')
        db.instance_get_all_by_host_and_node(ctxt, 'foo', 'bar').AndReturn(
            fakes)
        self.mox.ReplayAll()
        inst_list = instance.InstanceList.get_by_host_and_node(ctxt, 'foo',
                                                               'bar')
        for i in range(0, len(fakes)):
            self.assertTrue(isinstance(inst_list.objects[i],
                                       instance.Instance))
            self.assertEqual(inst_list.objects[i].uuid, fakes[i]['uuid'])
        self.assertRemotes()

    def test_get_by_host_and_not_type(self):
        fakes = [self.fake_instance(1),
                 self.fake_instance(2)]
        ctxt = context.get_admin_context()
        self.mox.StubOutWithMock(db, 'instance_get_all_by_host_and_not_type')
        db.instance_get_all_by_host_and_not_type(ctxt, 'foo',
                                                 type_id='bar').AndReturn(
                                                     fakes)
        self.mox.ReplayAll()
        inst_list = instance.InstanceList.get_by_host_and_not_type(ctxt, 'foo',
                                                                   'bar')
        for i in range(0, len(fakes)):
            self.assertTrue(isinstance(inst_list.objects[i],
                                       instance.Instance))
            self.assertEqual(inst_list.objects[i].uuid, fakes[i]['uuid'])
        self.assertRemotes()

    def test_get_hung_in_rebooting(self):
        fakes = [self.fake_instance(1),
                 self.fake_instance(2)]
        dt = timeutils.isotime()
        ctxt = context.get_admin_context()
        self.mox.StubOutWithMock(db, 'instance_get_all_hung_in_rebooting')
        db.instance_get_all_hung_in_rebooting(ctxt, dt).AndReturn(
            fakes)
        self.mox.ReplayAll()
        inst_list = instance.InstanceList.get_hung_in_rebooting(ctxt, dt)
        for i in range(0, len(fakes)):
            self.assertTrue(isinstance(inst_list.objects[i],
                                       instance.Instance))
            self.assertEqual(inst_list.objects[i].uuid, fakes[i]['uuid'])
        self.assertRemotes()


class TestInstanceListObject(test_objects._LocalTest,
                             _TestInstanceListObject):
    pass


class TestRemoteInstanceListObject(test_objects._RemoteTest,
                                   _TestInstanceListObject):
    pass
