# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

"""Smoke script for validating dynamic approval trigger behavior in an Odoo shell."""

model = env['ir.model']._get('res.partner')
approval_group = env.ref('sh_dynamic_approval.group_sh_dynamic_approval_admin')

approval_type = env['sh.approval.type'].create({
    'name': 'Smoke Partner Approval',
    'company_id': env.company.id,
    'model_id': model.id,
    'trigger_event': 'create',
    'domain_filter': "[('name', 'ilike', 'Smoke Approval Partner')]",
    'level_ids': [(0, 0, {
        'sequence': 10,
        'name': 'Administrator Approval',
        'approval_method': 'group',
        'group_id': approval_group.id,
    })],
})

partner = env['res.partner'].create({'name': 'Smoke Approval Partner'})
request = env['sh.approval.request'].search([
    ('res_model', '=', 'res.partner'),
    ('res_id', '=', partner.id),
    ('approval_type_id', '=', approval_type.id),
], limit=1)

assert request, 'Approval request was not created.'
assert request.state == 'pending', 'Approval request was not submitted.'
assert len(request.line_ids) == 1, 'Approval line was not created.'
assert request.log_ids.filtered(lambda log: log.action == 'triggered'), 'Triggered audit log is missing.'

print('SH_DYNAMIC_APPROVAL_SMOKE_OK request=%s partner=%s' % (request.id, partner.id))
