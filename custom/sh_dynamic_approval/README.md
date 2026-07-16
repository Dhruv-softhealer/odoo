# Dynamic Approval Engine

`sh_dynamic_approval` provides a centralized configurable approval engine for Odoo 19 Enterprise.

## Features

- Approval rules per Odoo model and company.
- Domain based rule matching.
- Create, update, both, and manual trigger support.
- Tracked update fields for write-trigger approvals.
- Update approvals stage proposed values and apply them only after final approval.
- Multi-level approval with sequence control.
- Approver resolution by access group, job position, or Python expression.
- Alternative approver and timeout escalation cron.
- Hierarchical auto-approval when senior approvers approve first.
- Refuse, modify, resubmit, cancel, and bulk approve flows.
- Approval dashboard and audit trail.
- Email templates for request, auto-approval, completion, refusal, escalation, and resubmission.
- Email approval links are token validated; email refusal collects a mandatory reason.
- ORM-level create/write interception with internal recursion guard.

## Configuration

Go to **Dynamic Approval > Configuration > Approval Types** and create an approval type.

1. Select the company and Odoo model.
2. Select trigger event.
3. Add an optional Odoo domain.
4. Select tracked update fields when update trigger is enabled.
5. Add at least one approval level.
6. Configure each level with an access group, job position, or Python expression.
7. Set alternative approver and escalation timeout where needed.

## Python Approver Context

Dynamic approver expressions receive:

- `record`: target business record.
- `env`: Odoo environment.
- `user`: requester user.

The expression must return `res.users`, `hr.employee`, a user id, or a list of user ids.

Example:

```python
record.employee_id.parent_id.user_id
```

## Notes

- Pending records are locked through ORM write interception.
- Configured update-triggered fields are held on the approval request until approval.
- Direct SQL changes bypass the approval engine.
- If multiple approval types match a record, the lowest sequence rule is used.
- Resubmission can reset all levels or only pending levels, based on the Approval Type setting.
