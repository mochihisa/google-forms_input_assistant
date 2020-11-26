from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageAction, PostbackAction, FollowEvent, MessageEvent, TextMessage,
    TextSendMessage, ImageMessage, ImageSendMessage, TemplateSendMessage,
    ButtonsTemplate, PostbackTemplateAction, MessageTemplateAction,
    URITemplateAction, URIAction, ConfirmTemplate
)
import os
import requests
import pickle
import textwrap
import subprocess
from pprint import pprint, pformat
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive


app = Flask(__name__)
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    res = main(event)
    res1 = TemplateSendMessage(
        alt_text='風邪症状の有無',
        template=ConfirmTemplate(
            title='風邪症状の有無',
            text='風邪症状の有無',
            actions=[
                MessageAction(
                    label='あり',
                    text='あり',
                ),
                MessageAction(
                    label='なし',
                    text='なし')
            ]
        )
    )
    res2 = TextSendMessage(text=res)
    message = res1 if res == '有無' else res2
    line_bot_api.reply_message(
        event.reply_token,
        message
    )


def sent(number, temperature, condition):
    #print(f'sent: {number=}, {temperature=}, {condition=}')
    d = {'entry.13709759': number,
         'entry.1796939242': temperature, 'entry.1087218957': condition}
    URL = 'https://docs.google.com/forms/u/0/d/e/1FAIpQLScru1V8aMZstu2wnpwY226VfZYD-dizIZqctmexaWxqa6xtvw/formResponse'
    response = requests.get(URL, params=d)
    return response.status_code


def save(filename, list):
    if filename == 'data' or filename == 'raw_data':
        with open(filename, mode='w') as f:
            f.write(str(list))
    else:
        with open(filename, 'wb') as f:
            pickle.dump(list, f)

    upload(filename)


def load(filename):
    download(filename)
    if filename == 'data' or filename == 'raw_data':
        with open(filename) as f:
            s = f.read()
        s = s.strip('{').strip('}').replace(' ', '')
        s = [s for s in s.split('],')]
        s = [[s.strip('[').strip(']') for s in s.split(':')] for s in s]
        s = [(s[0], s[1].split(',')) for s in s]
        s = [(s[0].strip("'"), [s.strip("'") for s in s[1]]) for s in s]
        dict = {}
        for s in s:
            dict[s[0]] = [s if s != 'None' else None for s in s[1]]
        return dict
    else:
        with open(filename, 'rb') as f:
            return pickle.load(f)


def download(filename):
    gauth = GoogleAuth()
    gauth.CommandLineAuth()
    drive = GoogleDrive(gauth)
    if filename == 'data':
        id = 'FILEID'
    elif filename == 'namelist':
        id = 'FILEID'
    elif filename == 'raw_data':
        id = 'FILEID'
    f = drive.CreateFile({'id': id})
    f.GetContentFile(filename)


def upload(filename):
    gauth = GoogleAuth()
    gauth.CommandLineAuth()
    drive = GoogleDrive(gauth)
    if filename == 'data':
        id = 'FILEID'
    elif filename == 'namelist':
        id = 'FILEID'
    elif filename == 'raw_data':
        id = 'FILEID'
    f = drive.CreateFile({
        'id': id,
        'title': filename
    })
    f.SetContentFile(filename)
    f.Upload()


def isnumber(number):
    try:
        float(number)
        return True
    except:
        return False


def getuser(event):
    profile = line_bot_api.get_profile(event.source.user_id)
    return event.source.user_id, profile.display_name


def broadcast(message):
    messages = TextSendMessage(text=message)
    line_bot_api.broadcast(messages=messages)


def whoami(event, command, namelist, *args):
    user_id, user_name = getuser(event)
    return f'{user_id=}\n{user_name=}\n{namelist[user_id]=}'


def temperature(number, data, dict):
    dict[number][0] = data
    save('data', dict)
    if dict[number][1] == None:
        return '有無'
    else:
        if sent(number, dict[number][0], dict[number][1]) == 200:
            return '送信完了'
        else:
            return '送信できませんでした\n入力しなおしてください.'


def condition(number, data, dict):
    # print(data)
    dict[number][1] = data
    save('data', dict)
    if data == 'あり':
        dict[number][1] = None
        save('data', dict)
        return textwrap.dedent(f'''\
        申し訳ありませんがこちらで入力してください.\n
        https://docs.google.com/forms/u/0/d/e/1FAIpQLScru1V8aMZstu2wnpwY226VfZYD-dizIZqctmexaWxqa6xtvw/formResponse\
?entry.13709759={number}\
&entry.1796939242={dict[number][0] if dict[number][0] != None else ""}\
        ''')
    elif dict[number][0] == None:
        return '体温を入力してください.'
    else:
        #print(number, dict[number][0], dict[number][1])
        if sent(number, dict[number][0], dict[number][1]) == 200:
            return '送信完了'
        else:
            return '送信できませんでした.\n入力しなおしてください.'


def help(*args):

    return textwrap.dedent('''\
    Commands:
    set  : set data
    help  : show helps
    feedback : sent feedback
    to : push
    say  : sent broadcast
    namelist  : show namelist
    data  : show data
    clear : clear data
    clear all  : clear all data
    whoami  : show user id and user name\
    ''')


def log(event, command):
    id, name = getuser(event)
    print(name, ':', command)


def set(command, namelist, userid, raw_data, data):
    if isnumber(command[1]):
        if userid in namelist:
            raw_data.pop(namelist[userid])
            data.pop(namelist[userid])
        namelist[userid] = command[1]
        raw_data[command[1]] = [None, None]
        data[command[1]] = [None, None]
        # print(namelist,data)
        save('raw_data', raw_data)
        save('namelist', namelist)
        save('data', data)
        return '設定完了'
    else:
        return '数字を入力してください.'


def push(user_id, message):

    messages = TextSendMessage(text=message)
    line_bot_api.push_message(user_id, messages=messages)


def feedback(event, command, *args):
    id, name = getuser(event)
    command.pop(0)
    message = id + '\n' + name + '\n' + ' '.join(command)
    push('Admin_user_id', message)
    return '送信が完了しました'


def admin(event, command, namelist, data):
    COMMANDS = {
        'say': say,
        'namelist': show_list,
        'data': show_list,
        'clear': clear,
        'to': to
    }
    userid, name = getuser(event)
    if userid in ['Admin_user_id']:
        return COMMANDS[command[0]](event, command, namelist, data)
    else:
        return f'{command[0]}: Permission denied'


def clear(event, command, *args):
    if len(command) >= 2:
        if command[1] == 'all':
            namelist = {'userid': 'number'}
            data = {'number': ['temperature', 'condition']}
            raw_data = {'number': ['temperature', 'condition']}
            save('namelist', namelist)
            save('data', data)
            save('raw_data', raw_data)
            return '正常に完了しました'
        else:
            return '引数が不正です'
    else:
        data = load('raw_data')
        save('data', data)
        return '正常に完了しました'


def show_list(event, command, namelist, data):
    if command[0] == 'namelist':
        return pformat(sorted(namelist.items(), key=lambda x: x[1]))
    if command[0] == 'data':
        return pformat(sorted(data.items()))


def say(event, command, *args):
    if len(command) >= 2:
        command.pop(0)
        broadcast(' '.join(command))
    return '正常に送信しました'


def to(event, command, *args):
    command.pop(0)
    userid = command.pop(0)
    message = ' '.join(command)
    push(userid, message)
    return '正常に送信しました'


def main(event):
    #namelist = load('namelist')
    #data = load('data')

    command = [s for s in event.message.text.split()]
    COMMANDS = {
        'say': admin,
        'whoami': whoami,
        'help': help,
        'namelist': admin,
        'data': admin,
        'clear': admin,
        'feedback': feedback,
        'to': admin
    }
    log(event, command)

    namelist = load('namelist')
    data = load('data')
    raw_data = load('raw_data')
    # subprocess.call('ls')
    #print(namelist, data, raw_data)
    userid, name = getuser(event)
    # print(userid)
    if command[0] == 'set':
        # print(namelist)
        return set(command, namelist, userid, raw_data, data)

    elif userid in namelist:
        number = namelist[userid]
        if isnumber(command[0]):
            return temperature(number, command[0], data)
        elif command[0] == 'あり' or command[0] == 'なし':
            return condition(number, command[0], data)
        elif command[0] in COMMANDS:
            return COMMANDS[command[0]](event, command, namelist, data)
        else:
            return f'{command[0]}: command not found'

    else:
        return '設定を完了させてください.\nset 名列番号(2年1組1番→2101)'


if __name__ == "__main__":
    port = int(os.getenv("PORT"))
    app.run(host="0.0.0.0", port=port)
