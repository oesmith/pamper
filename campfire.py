import base64
from datetime import date
from twisted.protocols import basic
from twisted.internet import protocol
from twisted.internet.task import LoopingCall
from pinder import Campfire

try:
    import simplejson as _json
except ImportError:
    try:
        import json as _json
    except ImportError:
        raise RuntimeError("A JSON parser is required, e.g., simplejson at "
                           "http://pypi.python.org/pypi/simplejson/")


class CampfireBot(object):
    """This is where all the actual message handling takes place.
    
    """
    def __init__(self, subdomain, room_name, token, ssl=False):
        self.campfire = Campfire(subdomain, token, ssl)
        self.room = self.campfire.find_room_by_name(room_name)
        self.me = self.campfire.me()
        self.auth_token = token
        self.xmpp = None
        if not self.room:
            raise RuntimeError("Could not find room %s" % room)
        self.users = {}
        self.joined = False

    def connectionMade(self):
        print "connectionMade"

    def connectionFailed(self, why):
        print "connectionFailed"

    def get_user(self, user_id):
        if user_id in self.users:
            return self.users[user_id]
        else:
            u = self.campfire.user(user_id)
            self.users[user_id] = u
            return u

    def formatMessage(self, msg):
        fwd_msg = None
        user = ('user_id' in msg and msg['user_id'] is not None) and self.get_user(msg['user_id']) or None
        if msg['type'] == 'TextMessage':
            fwd_msg = "%s: %s" % (user['user']['name'], msg['body'])
        elif msg['type'] == 'LeaveMessage' or msg['type'] == 'KickMessage':
            fwd_msg = "- %s has left the room" % user['user']['name']
        elif msg['type'] == 'EnterMessage':
            fwd_msg = "- %s has entered the room" % user['user']['name']
        elif msg['type'] == 'PasteMessage':
            fwd_msg = "- %s pasted:\n%s" % (user['user']['name'], msg['body'])
        elif msg['type'] == 'UploadMessage':
            fwd_msg = "- %s uploaded %s" % (user['user']['name'], msg['body'])
        elif msg['type'] == 'TimestampMessage':
            fwd_msg = "- timestamp %s" % (msg['created_at'])
        return fwd_msg

    def messageReceived(self, msg):
        print unicode(msg)
        if 'user_id' in msg and msg['user_id'] == self.me['id']:
            # skip my own messages
            if msg['type'] in ('TextMessage', 'PasteMessage'):
                return
        if msg['type'] in ('TextMessage', 'LeaveMessage', 'KickMessage', 'EnterMessage', 'PasteMessage', 'UploadMessage'):
            fwd_msg = self.formatMessage(msg)
            if fwd_msg:
                if self.xmpp:
                    self.xmpp.forwardMessage(fwd_msg)
                else:
                    print fwd_msg

    def _registerProtocol(self, protocol):
        self._streamProtocol = protocol

    def disconnect(self):
        print "disconnect"
        if hasattr(self, "_streamProtocol"):
            self._streamProtocol.factory.continueTrying = 0
            self._streamProtocol.transport.loseConnection()
        else:
            raise RuntimeError("not connected")
    
    def forwardMessage(self, msg):
        if msg[0] == "!":
            fwd_msg = "Unknown command"
            if msg == "!users":
                room = self.campfire.room(self.room.id)
                users = ', '.join([u['name'] for u in room.data['users']])
                fwd_msg = "Active users: %s" % users
            elif msg == "!uploads":
                files = self.room.uploads()
                file_str = '\n'.join([f['full_url'].replace(' ', '%20') for f in files])
                fwd_msg = "Uploaded files:\n%s" % file_str
            elif msg == "!room":
                fwd_msg = "Room URL: %s/room/%d" % (self.campfire.uri.geturl(),
                                                    self.room.id)
            elif msg == "!leave":
                self.leave()
                fwd_msg = "Left room"
            elif msg == "!join":
                self.join()
                fwd_msg = "Joined room"
            elif msg == "!transcript":
                today = date.today()
                fwd_msg = "Transcript URL: %s/room/%d/transcript/%04d/%02d/%02d" % (self.campfire.uri.geturl(),
                                                                                    self.room.id,
                                                                                    today.year,
                                                                                    today.month,
                                                                                    today.day)
            self.xmpp.forwardMessage("# %s" % fwd_msg)
        else:
            if '\n' in msg:
                self.room.paste(msg)
            else:
                self.room.speak(msg)

    def join(self):
        if self.room and not self.joined:
            self.joined = True
            self.room.join()
    
    def leave(self):
        if self.room and self.joined:
            self.joined = False
            self.room.leave()
    
    def keepAlive(self):
        if self.room and self.joined:
            self.room.join()

class CampfireStreamProtocol(basic.LineReceiver):
    delimiter = "\r"

    def __init__(self):
        self.in_header = True
        self.header_data = []
        self.status_data = ""
        self.status_size = None

    def connectionMade(self):
        self.transport.write(self.factory.header)
        self.factory.consumer._registerProtocol(self)

    def lineReceived(self, line):
        while self.in_header:
            if line:
                self.header_data.append(line)
            else:
                http, status, message = self.header_data[0].split(" ", 2)
                status = int(status)
                if status == 200:
                    self.factory.consumer.connectionMade()
                else:
                    self.factory.continueTrying = 0
                    self.transport.loseConnection()
                    self.factory.consumer.connectionFailed(RuntimeError(status, message))

                self.in_header = False
            break
        else:
            try:
                self.status_size = int(line, 16)
                self.setRawMode()
            except:
                pass

    def rawDataReceived(self, data):
        if len(data.strip()):
            print data

        if self.status_size is not None:
            data, extra = data[:self.status_size], data[self.status_size:]
            self.status_size -= len(data)
        else:
            extra = ""

        self.status_data += data
        if self.status_size == 0:
            for data_line in self.status_data.split(self.delimiter):
                try:
                    # ignore newline keep-alive
                    msg = _json.loads(data_line)
                except:
                    pass
                else:
                    self.factory.consumer.messageReceived(msg)
            self.status_data = ""
            self.status_size = None
            self.setLineMode(extra)


class CampfireStreamFactory(protocol.ReconnectingClientFactory):
    maxDelay = 120
    protocol = CampfireStreamProtocol
    keepAliveInterval = 300
    keepAliveLoopingCall = None

    def __init__(self, consumer):
        if isinstance(consumer, CampfireBot):
            self.consumer = consumer
        else:
            raise TypeError("consumer should be an instance of CampfireBot")
    
    def startFactory(self):
        # generate the HTTP headers
        auth = base64.encodestring("%s:x" % self.consumer.auth_token).strip()
        header = [
            "GET /room/%d/live.json HTTP/1.1" % self.consumer.room.id,
            "Authorization: Basic %s" % auth,
            "User-Agent: pamper",
            "Host: streaming.campfirenow.com",
        ]
        self.header = "\r\n".join(header) + "\r\n\r\n"
        # join the room and start the keepalive timer
        self.consumer.join()
        self.keepAliveLoopingCall = LoopingCall(self.consumer.keepAlive)
        self.keepAliveLoopingCall.start(self.keepAliveInterval)
    
    def stopFactory(self):
        self.keepAliveLoopingCall.stop()
        self.consumer.leave()
