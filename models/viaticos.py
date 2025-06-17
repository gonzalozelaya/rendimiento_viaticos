from odoo import models, fields, api, _

class HrExpense(models.Model):
    _inherit = 'hr.expense'

    amount_returned = fields.Monetary('Monto utilizado', default=0.0)
    
class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    rendimiento_ids = fields.One2many('hr.expense.rendimiento', 'sheet_id', string='Rendimientos')
    total_rendido = fields.Float('Total rendido', compute='_compute_total_rendido', store=True)
    saldo_pendiente = fields.Float('Saldo por rendir', compute='_compute_saldo_pendiente', store=True)
    rendimiento_count = fields.Integer(
        'Número de Rendimientos',
        compute='_compute_rendimiento_count',
        store=True
    )
    all_expenses_returned = fields.Boolean(
        string='Todos los gastos rendidos',
        compute='_compute_all_expenses_returned',
        store=True
    )
    total_amount_returned = fields.Monetary(
        'Total devuelto',
        compute='_compute_total_amount_returned',
        store=True
    )

    @api.depends('expense_line_ids.amount_returned')
    def _compute_total_amount_returned(self):
        for sheet in self:
            sheet.total_amount_returned = sum(sheet.expense_line_ids.mapped('amount_returned'))

    @api.depends('expense_line_ids.amount_returned')
    def _compute_all_expenses_returned(self):
        for sheet in self:
            if sheet.expense_line_ids:
                # Verifica que todas las líneas tengan amount_returned > 0
                sheet.all_expenses_returned = all(line.amount_returned > 0 for line in sheet.expense_line_ids)
            else:
                sheet.all_expenses_returned = False

    @api.depends('rendimiento_ids')
    def _compute_rendimiento_count(self):
        for sheet in self:
            sheet.rendimiento_count = len(sheet.rendimiento_ids)
            
    @api.depends('rendimiento_ids.amount')
    def _compute_total_rendido(self):
        for sheet in self:
            sheet.total_rendido = sum(sheet.rendimiento_ids.mapped('amount'))

    @api.depends('total_amount', 'total_rendido')
    def _compute_saldo_pendiente(self):
        for sheet in self:
            sheet.saldo_pendiente = sheet.total_amount - sheet.total_rendido

    def action_open_rendimiento_wizard(self):
        self.ensure_one()
        expense_lines = self.expense_line_ids.filtered(lambda line: line.amount_returned == 0)
        return {
            'name': _('Registrar Rendimiento'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'hr.expense.rendimiento.wizard',
            'target': 'new',
            'context': {
                'default_sheet_id': self.id,
                #'default_amount_paid': self.total_amount,
                #'default_amount_remaining': self.saldo_pendiente,
                'default_journal_id': self.journal_id.id,
                'default_payment_method_id':self.payment_method_line_id.id,
                'default_expense_line_ids':expense_lines.ids
            }
        }

    def action_open_rendimientos(self):
        self.ensure_one()
        
        # Obtener todos los rendimientos asociados a esta hoja
        rendimientos = self.rendimiento_ids
    
        # Abrir lista de rendimientos
        return {
            'name': _('Rendimientos'),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree',
            'res_model': 'hr.expense.rendimiento',
            'domain': [('id', 'in', rendimientos.ids)],
            'context': {'create': False},
            'target': 'current'
        }

    @api.depends('employee_id', 'employee_id.department_id')
    def _compute_from_employee_id(self):
        for sheet in self:
            sheet.department_id = sheet.employee_id.department_id
            sheet.user_id = self.env['res.users'].browse(30)

class HrExpenseRendimiento(models.Model):
    _name = 'hr.expense.rendimiento'
    _description = 'Rendimiento de viáticos'

    sheet_id = fields.Many2one('hr.expense.sheet', string='Hoja de gastos', required=True)
    date = fields.Date('Fecha', default=fields.Date.context_today, required=True)
    amount = fields.Float('Monto devuelto', required=True)
    move_id = fields.Many2one('account.move', string='Asiento contable')
    notes = fields.Text('Observaciones')

class RendimientoWizard(models.TransientModel):
    _name = 'hr.expense.rendimiento.wizard'
    _description = 'Wizard para registrar rendimiento de viáticos'

    
    sheet_id = fields.Many2one('hr.expense.sheet', string='Hoja de gastos', required=True)
    amount_paid = fields.Float('Monto pagado',compute='_compute_amount_paid', readonly=True)
    amount_used = fields.Float('Monto utilizado')
    amount_returned = fields.Float('Monto devuelto', compute='_compute_amount_returned', store=True)
    amount_remaining = fields.Float('Monto a recibir', readonly=True)
    date = fields.Date('Fecha', default=fields.Date.context_today, required=True)
    journal_id = fields.Many2one('account.journal', string='Diario', required=True, 
                               domain=[('type', 'in', ['bank', 'cash'])])
    payment_method_id = fields.Many2one('account.payment.method.line',string='Método de pago',readonly=True)
    notes = fields.Text('Observaciones')

    account_id = fields.Many2one('account.account',related='expense_id.account_id',string='Cuenta contable')
    expense_line_ids = fields.Many2many(
        'hr.expense',
        string='Líneas de gasto'
    )
    expense_id = fields.Many2one(
        'hr.expense',
        string='Gasto Seleccionado',
        domain="[('id', 'in', expense_line_ids)]"
    )

    @api.onchange('expense_line_ids')
    def _onchange_expense_line_ids(self):
        # Si hay líneas de gasto, selecciona la primera por defecto
        if self.expense_line_ids:
            self.expense_id = self.expense_line_ids[0].id
        else:
            self.expense_id = False
    
    @api.depends('amount_paid', 'amount_used')
    def _compute_amount_returned(self):
        for wizard in self:
            wizard.amount_returned = wizard.amount_paid - wizard.amount_used

    @api.depends('expense_id')
    def _compute_amount_paid(self):
        for wizard in self:
            if wizard.expense_id:
                wizard.amount_paid = wizard.expense_id.total_amount
            else:
                wizard.amount_paid = 0.0
        
    def action_register_rendimiento(self):
        self.ensure_one()
        
        if self.amount_used > self.amount_paid:
            raise UserError(_("El monto utilizado no puede ser mayor al monto pagado"))
        
        self.expense_id.write({'amount_returned':self.amount_returned})
        # Crear registro de rendimiento
        rendimiento = self.env['hr.expense.rendimiento'].create({
            'sheet_id': self.sheet_id.id,
            'date': self.date,
            'amount': self.amount_returned,
            'notes': self.notes,
        })

        # Crear asiento contable para el dinero devuelto
        move_lines = []
        
        # Línea para la cuenta del diario (haber - entrada de dinero)
        move_lines.append((0, 0, {
            'account_id': self.journal_id.default_account_id.id,
            'credit': 0,
            'debit': self.amount_returned,
            'name': _("Devolución de viático %s") % self.sheet_id.name,
        }))
        
        # Línea para la cuenta del empleado (debe - salida de dinero)
        partner = self.sheet_id.employee_id.sudo().work_contact_id
        #if not partner:
            #raise UserError(_("El empleado no tiene un contacto laboral configurado"))
            
        move_lines.append((0, 0, {
            'account_id': self.account_id.id,
            'credit': self.amount_returned,
            'debit': 0,
            'name': _("Devolución de viático %s") % self.sheet_id.name,
            #'partner_id': partner.id,
        }))
        
        move_vals = {
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': _("Devolución viático %s") % self.sheet_id.name,
            'line_ids': move_lines,
        }
        
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        
        # Vincular el asiento al registro de rendimiento
        rendimiento.move_id = move.id
        
        # Mostrar mensaje de confirmación
        
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'hr.expense.sheet',
            'res_id': self.sheet_id.id,
            'target': 'current',
        }

    