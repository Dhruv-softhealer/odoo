# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestShDynamicApproval(TransactionCase):
    """Test core dynamic approval business flows."""

    @classmethod
    def setUpClass(cls):
        """Prepare reusable model and group references."""
        super().setUpClass()
        cls.partner_model = cls.env['ir.model']._get('res.partner')
        cls.approval_group = cls.env.ref('sh_dynamic_approval.group_sh_dynamic_approval_admin')
        cls.approver_user = cls.env.ref('base.user_admin')
        cls.approval_group.write({'user_ids': [(4, cls.approver_user.id)]})

    def _create_partner_approval_type(self, name='Partner Approval', levels=1):
        """Create a partner approval type with one or more group-based levels."""
        level_commands = []
        for sequence in range(1, levels + 1):
            level_commands.append((0, 0, {
                'sequence': sequence * 10,
                'name': 'Level %s' % sequence,
                'approval_method': 'group',
                'group_id': self.approval_group.id,
            }))
        return self.env['sh.approval.type'].create({
            'name': name,
            'company_id': self.env.company.id,
            'model_id': self.partner_model.id,
            'trigger_event': 'create',
            'domain_filter': "[('name', 'ilike', '%s')]" % name,
            'level_ids': level_commands,
        })

    def _create_partner_approval_type_with_domain(self, name='Partner Approval', domain_filter='[]', levels=1):
        """Create a partner approval type with a custom domain."""
        approval_type = self._create_partner_approval_type(name=name, levels=levels)
        approval_type.write({'domain_filter': domain_filter})
        return approval_type

    def _create_manual_partner_approval_type(self, name='Manual Partner Approval'):
        """Create a manual-trigger approval type for partner records."""
        return self.env['sh.approval.type'].create({
            'name': name,
            'company_id': self.env.company.id,
            'model_id': self.partner_model.id,
            'trigger_event': 'manual',
            'domain_filter': '[]',
            'level_ids': [(0, 0, {
                'sequence': 10,
                'name': 'Manual Level',
                'approval_method': 'group',
                'group_id': self.approval_group.id,
            })],
        })

    def test_create_trigger_generates_pending_request(self):
        """Creating a matching record should create pending request, lines, and audit logs."""
        approval_type = self._create_partner_approval_type(name='Partner Trigger Test')
        partner = self.env['res.partner'].create({'name': 'Partner Trigger Test'})
        request = self.env['sh.approval.request'].search([
            ('approval_type_id', '=', approval_type.id),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', partner.id),
        ], limit=1)

        self.assertTrue(request)
        self.assertEqual(request.state, 'pending')
        self.assertEqual(len(request.line_ids), 1)
        self.assertTrue(request.log_ids.filtered(lambda log: log.action == 'triggered'))

    def test_higher_level_approval_auto_approves_lower_levels(self):
        """Approving a higher level should auto-approve lower pending levels."""
        approval_type = self._create_partner_approval_type(name='Partner Auto Approval Test', levels=3)
        partner = self.env['res.partner'].create({'name': 'Partner Auto Approval Test'})
        request = self.env['sh.approval.request'].search([
            ('approval_type_id', '=', approval_type.id),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', partner.id),
        ], limit=1)

        level_three = request.line_ids.filtered(lambda line: line.sequence == 30)
        level_three.write({'approver_ids': [(6, 0, self.approver_user.ids)]})
        request.invalidate_recordset()
        level_three.invalidate_recordset()
        request = request.browse(request.id)
        request.with_user(self.approver_user).action_approve()

        self.assertEqual(request.state, 'approved')
        self.assertEqual(
            request.line_ids.filtered(lambda line: line.sequence in (10, 20)).mapped('state'),
            ['auto_approved', 'auto_approved'],
        )
        self.assertEqual(level_three.state, 'approved')

    def test_signed_action_url_contains_token(self):
        """Email action URLs should be signed per recipient user."""
        approval_type = self._create_partner_approval_type_with_domain(name='Partner Token Test', domain_filter='[]')
        partner = self.env['res.partner'].create({'name': 'Partner Token Test'})
        request = self.env['sh.approval.request'].search([
            ('approval_type_id', '=', approval_type.id),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', partner.id),
        ], limit=1)

        url = request.with_context(sh_approval_recipient_user_id=self.approver_user.id)._get_action_url('approve')
        self.assertIn('uid=%s' % self.approver_user.id, url)
        self.assertIn('token=', url)

    def test_bulk_action_is_bound_to_list_view(self):
        """Bulk approval must be exposed as a server action in the list view."""
        action = self.env.ref('sh_dynamic_approval.action_server_sh_dynamic_approval_bulk_approve')
        self.assertEqual(action.binding_type, 'action')
        self.assertEqual(action.binding_view_types, 'list')
        self.assertEqual(action.model_id.model, 'sh.approval.request')

    def test_manual_approval_generates_bound_server_action(self):
        """Manual approval types must generate a bound action on the target model."""
        approval_type = self._create_manual_partner_approval_type(name='Manual Partner Action Test')
        action = self.env['ir.actions.server'].search([
            ('name', '=', '%s - Manual Submit for Approval' % approval_type.name),
            ('model_id', '=', approval_type.model_id.id),
            ('binding_model_id', '=', approval_type.model_id.id),
        ], limit=1)

        self.assertTrue(action)
        self.assertEqual(action.binding_view_types, 'form')

    def test_resubmission_records_modification_summary(self):
        """Resubmission should capture field-level changes in the audit summary."""
        approval_type = self._create_partner_approval_type_with_domain(name='Partner Resubmit Test', domain_filter='[]')
        partner = self.env['res.partner'].create({'name': 'Partner Resubmit Test'})
        request = self.env['sh.approval.request'].search([
            ('approval_type_id', '=', approval_type.id),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', partner.id),
        ], limit=1)

        request.line_ids.write({'approver_ids': [(6, 0, self.approver_user.ids)]})
        request.with_user(self.approver_user)._refuse_by_user(self.approver_user, 'Needs correction')
        request.action_modify()
        partner.write({'name': 'Partner Resubmit Test Updated'})
        request.action_resubmit()

        self.assertTrue(request.modification_summary)
        self.assertIn('name', request.modification_summary)

    def test_delegate_action_is_logged(self):
        """Actions taken by an alternative approver must be marked as delegated in the audit trail."""
        approval_type = self._create_partner_approval_type_with_domain(name='Partner Delegate Test', domain_filter='[]')
        partner = self.env['res.partner'].create({'name': 'Partner Delegate Test'})
        delegate_user = self.env['res.users'].with_context(sh_skip_dynamic_approval=True).create({
            'name': 'Delegate User',
            'login': 'delegate.user@example.com',
            'email': 'delegate.user@example.com',
        })
        delegate_user.with_context(sh_skip_dynamic_approval=True).write({
            'group_ids': [(4, self.approval_group.id)],
        })
        request = self.env['sh.approval.request'].search([
            ('approval_type_id', '=', approval_type.id),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', partner.id),
        ], limit=1)

        request.line_ids.write({
            'approver_ids': [(6, 0, delegate_user.ids)],
            'alternative_user_id': delegate_user.id,
        })
        request.with_user(delegate_user).action_approve()
        request.invalidate_recordset()
        request = request.browse(request.id)

        delegated_logs = request.log_ids.filtered(lambda log: 'delegated' in (log.note or '').lower())
        self.assertTrue(delegated_logs)

    def test_authorized_user_can_force_approve(self):
        """Authorized users must be able to force approve a pending request."""
        approval_type = self._create_partner_approval_type(name='Partner Force Approve Test', levels=2)
        partner = self.env['res.partner'].create({'name': 'Partner Force Approve Test'})
        request = self.env['sh.approval.request'].search([
            ('approval_type_id', '=', approval_type.id),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', partner.id),
        ], limit=1)

        self.env['sh.approval.engine'].with_user(self.approver_user).action_force_approve(request)
        request.invalidate_recordset()
        request = request.browse(request.id)

        self.assertEqual(request.state, 'approved')
        self.assertTrue(request.log_ids.filtered(lambda log: log.action == 'completed'))

    def test_escalation_without_alternative_notifies_intervention_path(self):
        """Escalation must still run when no alternative approver is configured."""
        approval_type = self._create_partner_approval_type(name='Partner Escalation Fallback Test', levels=1)
        approval_type.level_ids.write({
            'escalation_timeout': 1.0,
            'alternative_user_id': False,
        })
        partner = self.env['res.partner'].create({'name': 'Partner Escalation Fallback Test'})
        request = self.env['sh.approval.request'].search([
            ('approval_type_id', '=', approval_type.id),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', partner.id),
        ], limit=1)

        self.env.cr.execute(
            "UPDATE sh_approval_line SET create_date = NOW() - INTERVAL '2 hours' WHERE request_id = %s",
            (request.id,),
        )
        request._process_escalation_line(request.line_ids[:1])
        request.invalidate_recordset()
        request = request.browse(request.id)

        self.assertEqual(request.line_ids.filtered(lambda line: line.level_id.escalation_timeout).state, 'escalated')
        self.assertTrue(request.log_ids.filtered(lambda log: 'intervention' in (log.note or '').lower()))

    def test_pending_lines_are_not_emailed_twice(self):
        """Approving a lower level must not resend already-notified upper level emails."""
        approval_type = self._create_partner_approval_type(name='Partner Email Guard Test', levels=2)
        partner = self.env['res.partner'].create({'name': 'Partner Email Guard Test'})
        request = self.env['sh.approval.request'].search([
            ('approval_type_id', '=', approval_type.id),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', partner.id),
        ], limit=1)

        lower_user = self.env['res.users'].with_context(sh_skip_dynamic_approval=True).create({
            'name': 'Lower Approver',
            'login': 'lower.approver@example.com',
            'email': 'lower.approver@example.com',
        })
        upper_user = self.env['res.users'].with_context(sh_skip_dynamic_approval=True).create({
            'name': 'Upper Approver',
            'login': 'upper.approver@example.com',
            'email': 'upper.approver@example.com',
        })
        lower_user.with_context(sh_skip_dynamic_approval=True).write({
            'group_ids': [(4, self.approval_group.id)],
        })
        upper_user.with_context(sh_skip_dynamic_approval=True).write({
            'group_ids': [(4, self.approval_group.id)],
        })
        request.line_ids.filtered(lambda line: line.sequence == 10).write({'approver_ids': [(6, 0, lower_user.ids)]})
        request.line_ids.filtered(lambda line: line.sequence == 20).write({
            'approver_ids': [(6, 0, upper_user.ids)],
            'notification_date': fields.Datetime.now()
        })

        initial_email_count = len(request.log_ids.filtered(lambda log: log.action == 'email_sent'))
        request.with_user(lower_user).action_approve()
        request.invalidate_recordset()
        request = request.browse(request.id)

        self.assertEqual(
            len(request.log_ids.filtered(lambda log: log.action == 'email_sent')),
            initial_email_count,
        )
