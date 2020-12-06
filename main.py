#coding:utf-8
import sys, time, json, os, traceback, random, math, tempfile, uuid, pinyin
from flask import Flask, render_template, g, request, redirect, make_response, session, url_for

reload(sys)
sys.setdefaultencoding( "utf-8" )

# DEBUG = True
# FLATPAGES_AUTO_RELOAD = DEBUG

app = Flask(__name__)
app.config.from_object(__name__)
app.secret_key = 'nzi*HJfy&edetFh1m58pQDUU0ZHFjRMH1TI4nePtEZYNYyNHtrssZgemnin0RnrF'

first_alpha = lambda name:"".join([i[0].lower() for i in pinyin.get(name, " ", format='strip').split() if i[0].lower() in 'abcdefghijklmnopqrstuvwxyz0123456789'])

class DB():
    def __init__(self):
        with open("./db/goods.db", "r") as f:
            self.db = json.loads(f.read())
        return

    def __refresh(self):
        with open("./db/goods.db", "r") as f:
            self.db = json.loads(f.read())
        return

    def goods(self):
        return self.db["goods"]

    def goods_item(self, id):
        for i, good in enumerate(self.db['goods']):
            if good['id'] == id:
                return good
        return None

    def attrs(self):
        return self.db["attrs"]

    def update_attrs(self, attr):
        for _attr in self.db['attrs']:
            if _attr['id'] == attr['id']:
                _attr['opts'] = attr['opts']
                break
        return self.__update()


    def __update(self):
        with open("./db/goods.db", "w") as f:
            f.write(json.dumps(self.db, indent=4))
        return self.__refresh()

    def delete_goods(self, id):
        for i, good in enumerate(self.db['goods']):
            if good['id'] == id:
                self.db['goods'].pop(i)
                break
        return self.__update()

    def state_goods(self, id, state):
        for good in self.db['goods']:
            if good['id'] == id:
                good['state'] = state
                break
        return self.__update()

    def update_goods(self, good):
        for _good in self.db['goods']:
            if _good['id'] == good['id']:
                _good['name']  = good['name']
                _good['attr']  = good['attr']
                _good['info']  = good['info']
                break
        return self.__update()

    def create_goods(self, good):
        self.db['goods'].append(good)
        return self.__update()

    def add_attr_opt(self, attr_id, name):
        for attr in self.db['attrs']:
            if int(attr['id']) != attr_id:
                continue
            idx = 1 if attr['opts'] == [] else max([int(opt['id']) for opt in attr['opts']]) + 1
            attr['opts'].append({'id':idx, 'value':name})
        return idx

# 权限错误
class AuthorityException(Exception):
    def __init__(self, err):
        Exception.__init__(self, err)

@app.errorhandler(AuthorityException)
def err_runtimeerror(err):
    return render_template('admin-login.html', info=err)

# 权限验证
def check_authority():
    if 'user_name' not in session:
        raise AuthorityException("operation not authorized")

def is_admin():
    if 'user_name' in session and session['user_name'] == "admin":
        return True
    return False

def is_user():
    if 'user_name' in session and session['user_name'] == "user":
        return True
    return False

@app.route('/')
def index():
    check_authority()
    db = DB()
    attrs = db.attrs()
    # 补充首字母

    # 基本味特征2
    attr_5 = {}
    for attr in [attr for attr in attrs if attr['id'] == 5]:
        for opt in attr['opts']:
            attr_5[str(opt['id'])] = opt['value']

    # 风险风味
    attr_6 = {}
    for attr in [attr for attr in attrs if attr['id'] == 6]:
        for opt in attr['opts']:
            attr_6[str(opt['id'])] = opt['value']

    def __get_tip(attr):
        out = ""
        tip = []
        if '5' in attr.keys():
            for a in attr['5']:
                if str(a) in attr_5.keys():
                    tip.append(attr_5[str(a)])
        if tip != []:
            out += "+".join(tip) + "。"
        tip = []
        if '6' in attr.keys():
            for a in attr['6']:
                if str(a) in attr_6.keys():
                    tip.append(attr_6[str(a)])
        if tip != []:
            out += "风险风味：" + "，".join(tip)
        return out

    def __fix_info(info):
        return info.replace(' ', '&nbsp;').replace('\n', '<br>')

    goods = []
    for good in db.goods():
        good['first_alpha'] = first_alpha(good['name'])
        good['tip']         = __get_tip(good['attr'])
        good['info']        = __fix_info(good['info'] if good.has_key('info') else "")
        goods.append(good)
    return render_template('index.html', attrs=attrs, goods=goods, admin=is_admin(), user=is_user())

@app.route('/admin/goods')
def goods():
    check_authority()
    db = DB()
    goods = db.goods()
    attrs = db.attrs()
    return render_template('edit.html', attrs=attrs, goods=goods, enumerate=enumerate, admin=is_admin(), user=is_user())

@app.route('/admin/goods/create', methods=['POST', 'GET'])
def goods_create():
    check_authority()
    db = DB()
    if request.method == "GET":
        attrs = db.attrs()
        return render_template('add-goods.html', attrs=attrs, admin=is_admin(), user=is_user())
    else:
        user_define_attrs = {}
        for attr, value in request.json['defs'].items():
            user_define_attrs[int(attr)] = db.add_attr_opt(int(attr), value)

        good = {}
        good["name"]  = request.json['name'].strip()
        good["info"]  = request.json['info']
        good["id"]    = str(uuid.uuid1())
        good["state"] = 1
        good["attr"] = {}
        for attr, opt in request.json['opts'].items():
            attr = int(attr)
            good["attr"][attr] = opt
            if attr in user_define_attrs.keys():
                good["attr"][attr].append(user_define_attrs[attr])
        db.create_goods(good)
        return json.dumps({'result':True})

@app.route('/admin/attr/delete', methods=['POST', 'GET'])
def attr_delete():
    check_authority()
    db = DB()
    if request.method == "GET":
        attrs = db.attrs()
        return render_template('delete-attr.html', attrs=attrs, admin=is_admin(), user=is_user())
    else:
        def is_delete(attr_id, opt_id):
            attr_id = int(attr_id)
            opt_id  = int(opt_id)
            flag = False
            for attr, opts in request.json['opts'].items():
                if int(attr) != attr_id:
                    continue
                for opt in opts:
                    if int(opt) == opt_id:
                        flag = True
            return flag

        # 遍历所有goods删除目标属性
        for good in db.goods():
            for attr, opts in good['attr'].items():
                for opt in opts:
                    if is_delete(attr, opt) == True:
                        opts.remove(opt)
            db.update_goods(good)

        # 遍历所有goods删除目标属性
        for attr in db.attrs():
            attr_id = attr['id']
            opts    = attr['opts']
            for opt in opts:
                opt_id = opt['id']
                if is_delete(attr_id, opt_id) == True:
                    opts.remove(opt)
            db.update_attrs(attr)
        return json.dumps({'result':True})

@app.route('/admin/goods/delete/<string:id>')
def goods_delete(id):
    check_authority()
    db = DB()
    db.delete_goods(id)
    goods = db.goods()
    attrs = db.attrs()
    return render_template('edit.html', attrs=attrs, goods=goods, enumerate=enumerate, admin=is_admin(), user=is_user())

@app.route('/admin/goods/state/<string:id>/<string:state>')
def goods_online(id, state):
    check_authority()
    db = DB()
    db.state_goods(id, int(state))
    goods = db.goods()
    attrs = db.attrs()
    return render_template('edit.html', attrs=attrs, goods=goods, enumerate=enumerate, admin=is_admin(), user=is_user())

@app.route('/admin/goods/update/<string:id>', methods=['GET'])
def goods_update_get(id):
    check_authority()
    db = DB()
    attrs = db.attrs()
    good  = db.goods_item(id)
    return render_template('update-goods.html', attrs=attrs, good=good, admin=is_admin(), user=is_user())

@app.route('/admin/goods/update', methods=['POST'])
def goods_update():
    check_authority()
    db = DB()

    user_define_attrs = {}
    for attr, value in request.json['defs'].items():
        user_define_attrs[int(attr)] = db.add_attr_opt(int(attr), value)

    good = {}
    good["name"]  = request.json['name'].strip()
    good["info"]  = request.json['info']
    good["id"]    = request.json['id']
    good["attr"] = {}
    for attr, opt in request.json['opts'].items():
        attr = int(attr)
        good["attr"][attr] = opt
        if attr in user_define_attrs.keys():
            good["attr"][attr].append(user_define_attrs[attr])
    db.update_goods(good)
    return json.dumps({'result':True})

@app.route('/admin/goods/list')
def list():
    check_authority()
    db = DB()
    goods = db.goods()
    attrs = db.attrs()

    key_attrs  = {}
    attrs_name = []
    attrs_name_kv = {}
    for attr in attrs:
        attrs_name.append((str(attr['id']), attr['name']))
        attrs_name_kv[attr['id']] = attr['name']
        for opt in attr['opts']:
            key_attrs["%s.%s" % (attr['id'], opt['id'])] = opt['value']
    attrs_name.sort()

    items = []
    for good in goods:
        item = {}
        item['name'] = good['name']
        item['opts'] = {}
        for key, values in good['attr'].items():
            attr_name = []
            for value in values:
                if "%s.%s" % (key, value) in key_attrs.keys():
                    attr_name.append(key_attrs["%s.%s" % (key, value)])
            item['opts'][key] = ",".join(attr_name)
        for k, v in attrs_name_kv.items():
            if str(k) not in item['opts'].keys():
                item['opts'][str(k)] = ''
        items.append(item)
    return render_template('list.html', items=items, attrs_name=attrs_name,  enumerate=enumerate, len=len, admin=is_admin(), user=is_user())

@app.route('/admin/login', methods=['POST', 'GET'])
def user_login():
    if request.method == 'GET':
        return render_template('admin-login.html', info="")
    pass2user = {
        "admin" : "admin",
        "123456" : "user",
    }
    if request.form['pass_word'] not in pass2user.keys():
        return render_template('admin-login.html', info="password error")
    session['user_name'] = pass2user[request.form['pass_word']]
    return redirect(url_for('index'))

@app.route('/admin/logout', methods=['GET'])
def user_logout():
    session.pop('user_name', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(threaded=True, debug=True, host="0.0.0.0", port=7777)
