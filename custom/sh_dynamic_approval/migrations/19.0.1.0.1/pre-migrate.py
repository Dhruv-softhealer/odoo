def migrate(cr, version):
    """
    Scrub references to the deprecated group so it can be safely deleted 
    by the Odoo ORM when it parses the updated XML without crashing on 
    Foreign Key constraints.
    """
    cr.execute("""
        DELETE FROM rule_group_rel 
        WHERE group_id IN (
            SELECT res_id FROM ir_model_data 
            WHERE module = 'sh_dynamic_approval' AND name = 'group_sh_dynamic_approval_authorized_user'
        );
    """)
    # Optional safety for users relation just in case
    cr.execute("""
        DELETE FROM res_groups_users_rel
        WHERE gid IN (
            SELECT res_id FROM ir_model_data 
            WHERE module = 'sh_dynamic_approval' AND name = 'group_sh_dynamic_approval_authorized_user'
        );
    """)
