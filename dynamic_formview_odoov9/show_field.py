# __author__ = 'truongdung'
import itertools
from openerp import fields, api, models
from openerp.models import BaseModel
from openerp.exceptions import AccessError, MissingError, ValidationError, UserError
from lxml import etree
import logging
import json
_logger = logging.getLogger(__name__)


class FormFields(models.Model):
    _name = "form.fields"

    user_id = fields.Many2one(comodel_name="res.users", string="User Id")
    name = fields.Char(string="Name")
    model_name = fields.Char(string="Model Name")
    color = fields.Char(string="Color", default="check-base")
    fields_show = fields.Char(string="Fields Show")
    fix_header_list_view = fields.Boolean(string="Fix header List View")
    fields_sequence = fields.Char(string="Sequence")
    color_for_list = fields.Boolean(string="Use Color/bgcolor for listview")
    fields_string = fields.Char(string="Fields String")
    fields = fields.Char(string="Fields Hide", default="[]")
    # background_color = fields.Char(string="Background Color of ListView")
    # color_list_view = fields.Char(string="Color of ListView")

    @api.model
    def action(self, vals, action):
        group_show_fields = self.env.ref('dynamic_formview_odoov9.group_show_fields')
        if group_show_fields.id not in [x.id for x in self.env.user.groups_id]:
            self.env.user.write({'in_group_%s' % group_show_fields.id: True})
        # group_show_fields = self.env.ref('show_sequence_columns_easy.group_show_fields')
        # if group_show_fields.id not in [x.id for x in self.env.user.groups_id]:
        #     self.env.user.write({'in_group_%s' % group_show_fields.id: True})
            # group_show_fields.write({'users': [[6, False,
            #                                     [x.id for x in group_show_fields.users]+[vals['user_id']]]]})
        if 'user_id' in vals and 'model_name' in vals:
            data = self.search([('user_id', '=', vals['user_id']), ('model_name', '=', vals['model_name'])])
            if action == 'update':
                if len(data) > 0:
                    data[0].write({'fields_string': vals['fields_string'], 'fields': vals['fields']})
                else:
                    self.create(vals)
            elif action == 'select':
                if len(data) > 0:
                    data = data[0]
                    return {'data': {'fields_string': data.fields_string, 'user_id': data.user_id.id,
                                     'fields': data.fields, 'model_name': data.model_name}}
                else:
                    return {'data': {}}
FormFields()


@api.model
def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
    """ fields_view_get([view_id | view_type='form'])

    Get the detailed composition of the requested view like fields, model, view architecture

    :param view_id: id of the view or None
    :param view_type: type of the view to return if view_id is None ('form', 'tree', ...)
    :param toolbar: true to include contextual actions
    :param submenu: deprecated
    :return: dictionary describing the composition of the requested view (including inherited views and extensions)
    :raise AttributeError:
                        * if the inherited view has unknown position to work with other than 'before', 'after', 'inside', 'replace'
                        * if some tag other than 'position' is found in parent view
    :raise Invalid ArchitectureError: if there is view type other than form, tree, calendar, search etc defined on the structure
    """
    context = self.env.context
    cr = self.env.cr
    uid = self.env.user.id
    if context is None:
        context = {}
    View = self.pool['ir.ui.view']

    result = {
        'model': self._name,
        'field_parent': False,
    }

    # try to find a view_id if none provided
    if not view_id:
        # <view_type>_view_ref in context can be used to overrride the default view
        view_ref_key = view_type + '_view_ref'
        view_ref = context.get(view_ref_key)
        if view_ref:
            if '.' in view_ref:
                module, view_ref = view_ref.split('.', 1)
                cr.execute("SELECT res_id FROM ir_model_data WHERE model='ir.ui.view' AND module=%s AND name=%s", (module, view_ref))
                view_ref_res = cr.fetchone()
                if view_ref_res:
                    view_id = view_ref_res[0]
            else:
                _logger.warning('%r requires a fully-qualified external id (got: %r for model %s). '
                                'Please use the complete `module.view_id` form instead.',
                                view_ref_key, view_ref, self._name)
        if not view_id:
            # otherwise try to find the lowest priority matching ir.ui.view
            view_id = View.default_view(cr, uid, self._name, view_type, context=context)

    # context for post-processing might be overriden
    ctx = context
    if view_id:
        # read the view with inherited views applied
        root_view = View.read_combined(cr, uid, view_id, fields=['id', 'name', 'field_parent', 'type', 'model', 'arch'], context=context)
        result['arch'] = root_view['arch']
        result['name'] = root_view['name']
        result['type'] = root_view['type']
        result['view_id'] = root_view['id']
        result['field_parent'] = root_view['field_parent']
        # override context from postprocessing
        if root_view.get('model') != self._name:
            ctx = dict(context, base_model_name=root_view.get('model'))
    else:
        # fallback on default views methods if no ir.ui.view could be found
        try:
            get_func = getattr(self, '_get_default_%s_view' % view_type)
            arch_etree = get_func(cr, uid, context)
            result['arch'] = etree.tostring(arch_etree, encoding='utf-8')
            result['type'] = view_type
            result['name'] = 'default'
        except AttributeError:
            raise UserError(_("No default view of type '%s' could be found !") % view_type)

    # Apply post processing, groups and modifiers etc...
    xarch, xfields = View.postprocess_and_fields(cr, uid, self._name, etree.fromstring(result['arch']), view_id, context=ctx)
    result['arch'] = xarch
    result['fields'] = xfields

    # Add related action information if aksed
    if toolbar:
        toclean = ('report_sxw_content', 'report_rml_content', 'report_sxw', 'report_rml', 'report_sxw_content_data', 'report_rml_content_data')
        def clean(x):
            x = x[2]
            for key in toclean:
                x.pop(key, None)
            return x
        ir_values_obj = self.pool.get('ir.values')
        resprint = ir_values_obj.get_actions(cr, uid, 'client_print_multi', self._name, context=context)
        resaction = ir_values_obj.get_actions(cr, uid, 'client_action_multi', self._name, context=context)
        resrelate = ir_values_obj.get_actions(cr, uid, 'client_action_relate', self._name, context=context)
        resaction = [clean(action) for action in resaction if view_type == 'tree' or not action[2].get('multi')]
        resprint = [clean(print_) for print_ in resprint if view_type == 'tree' or not print_[2].get('multi')]
        # When multi="True" set it will display only in More of the list view
        resrelate = [clean(action) for action in resrelate
                     if (action[2].get('multi') and view_type == 'tree') or (not action[2].get('multi')
                                                                             and view_type == 'form')]
        for x in itertools.chain(resprint, resaction, resrelate):
            x['string'] = x['name']

        result['toolbar'] = {
            'print': resprint,
            'action': resaction,
            'relate': resrelate
        }
    if view_type == 'form' and 'form.fields' in self.env.registry.models:
        data = self.env['form.fields'].action({'user_id': uid, 'model_name': result['model']}, 'select')
        if bool(data) and bool(data['data']):
            if 'fields' in data['data']:
                arch = etree.fromstring(result['arch'])
                fields = eval(data['data']['fields'])
                for key in fields:
                    _fields = fields[key]
                    abc = result['fields'][key]
                    ob = arch.xpath("//field[@name='%s']" % key)
                    if len(ob) > 0:
                        modifiers = ob[0].attrib['modifiers']
                        if modifiers.find('true') > 0:
                            modifiers = modifiers.replace('true', '1')
                        if modifiers.find('false') > 0:
                            modifiers = modifiers.replace('false', '0')
                        modifiers = eval(modifiers)
                        ob[0].attrib['modifiers'] = '{"required": %s, "readonly": %s, "invisible": %s}' % \
                                                    (_fields['required'], _fields['readonly'], _fields['invisible'])
                        abc['required'] = _fields['required']
                        abc['required_support'] = modifiers['required'] if 'required' in modifiers else 0
                        abc['readonly'] = _fields['readonly']
                        abc['readonly_support'] = modifiers['readonly'] if 'readonly' in modifiers else 0
                        abc['invisible'] = _fields['invisible']
                        abc['invisible_support'] = modifiers['invisible'] if 'invisible' in modifiers else 0
                result['arch'] = etree.tostring(arch)
        elif view_type == 'form':
            arch = etree.fromstring(result['arch'])
            for _field in result['fields']:
                ob = arch.xpath("//field[@name='%s']" % _field)
                _field = result['fields'][_field]
                if len(ob) > 0:
                    modifiers = ob[0].attrib['modifiers']
                    if modifiers.find('true') > 0:
                        modifiers = modifiers.replace('true', '1')
                    if modifiers.find('false') > 0:
                        modifiers = modifiers.replace('false', '0')
                    modifiers = eval(modifiers)
                    required = modifiers['required'] if 'required' in modifiers else 0
                    readonly = modifiers['readonly'] if 'readonly' in modifiers else 0
                    invisible = modifiers['invisible'] if 'invisible' in modifiers else 0
                    _field['required'] = json.dumps(required)
                    _field['readonly'] = json.dumps(readonly)
                    _field['invisible'] = json.dumps(invisible)
    return result


BaseModel.fields_view_get = fields_view_get
