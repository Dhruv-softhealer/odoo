# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import http
from odoo.http import request
from odoo.tools import html_escape


class ShApprovalController(http.Controller):
    """Token-validated approval routes for email-driven workflow actions."""

    @http.route(
        '/sh_dynamic_approval/request/<int:request_id>/<string:action>',
        type='http',
        auth='public',
        csrf=True,
        methods=['GET', 'POST'],
    )
    def action_request(self, request_id, action, **kwargs):
        """Approve, refuse, or view an approval request from a signed email link."""
        approval_request = request.env['sh.approval.request'].sudo().browse(request_id).exists()
        if not approval_request or action not in ('approve', 'refuse', 'view'):
            return request.not_found()
        uid = int(kwargs.get('uid') or 0)
        token = kwargs.get('token')
        if not approval_request._check_action_token(action, uid, token):
            return request.not_found()

        if not request.session.uid:
            import urllib.parse
            redirect_url = f'/sh_dynamic_approval/request/{request_id}/{action}'
            query_params = []
            if uid: query_params.append(f'uid={uid}')
            if token: query_params.append(f'token={token}')
            if query_params: redirect_url += '?' + '&'.join(query_params)
            return request.redirect('/web/login?redirect=' + urllib.parse.quote(redirect_url))

        if action == 'view':
            return request.redirect('/web#id=%s&model=sh.approval.request&view_type=form' % approval_request.id)

        # SECURITY: Always execute the action as the currently logged-in user, 
        # not the user the email was originally sent to (in case the link was forwarded or leaked).
        approver = request.env.user

        from odoo.exceptions import UserError

        if action == 'refuse':
            action_rec = request.env.ref('sh_dynamic_approval.action_sh_approval_refuse_wizard', raise_if_not_found=False)
            if action_rec:
                import urllib.parse
                import json
                ctx = urllib.parse.quote(json.dumps({'default_is_from_email': True}))
                url = '/web#action=%s&active_id=%s&active_model=sh.approval.request&context=%s' % (action_rec.id, approval_request.id, ctx)
                return request.redirect(url)
            return request.redirect('/web#id=%s&model=sh.approval.request&view_type=form' % approval_request.id)

        if action == 'approve':
            # As per requirements, do not directly approve from the link.
            # Instead, simply redirect to the form view where UI access rights apply.
            return request.redirect('/web#id=%s&model=sh.approval.request&view_type=form' % approval_request.id)

    @http.route('/sh_dynamic_approval/close_window', type='http', auth='public')
    def close_window(self):
        return request.make_response(
            """
            <html><body>
                <script>
                    window.close();
                </script>
                <h2>Action Completed</h2>
                <p>You may safely close this window.</p>
            </body></html>
            """,
            headers=[('Content-Type', 'text/html; charset=utf-8')]
        )
