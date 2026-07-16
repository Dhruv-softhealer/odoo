def test_mapped(env):
    employees = env['hr.employee'].search([('id', '=', 999999)])
    users = employees.mapped('user_id')
    print("Users:", users)
