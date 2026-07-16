# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from .sh_test_dynamic_approval import TestShDynamicApproval as ShBaseTestDynamicApproval


class TestShDynamicApproval(ShBaseTestDynamicApproval):
    """Odoo test discovery wrapper for the sh-prefixed test implementation."""

    allow_inherited_tests_method = True
