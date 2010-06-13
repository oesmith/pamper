import base64
from twisted.protocols import basic
from twisted.internet import protocol
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
    def __init__(self, subdomain, room_name, token, ssl=False):
        self.campfire = Campfire(subdomain, token, ssl)
        self.room = self.campfire.find_room_by_name(room_name)
        self.me = self.campfire.me()
        self.auth_token = token
        self.xmpp = None
        if not self.room:
            raise RuntimeError("Could not find room %s" % room)
        self.users = {}

    def connectionMade(self):
        print "connectionMade"

    def connectionFailed(self, why):
        print "connectionFailed"

    def get_user(self, user_id):
        if user_id in self.users:
            return self.users[user_id]
        else:
            return self.campfire.user(user_id)

    def messageReceived(self, msg):
        print unicode(msg)
        if 'user_id' in msg and msg['user_id'] == self.me['id']:
            # skip my own messages
            return
        fwd_msg = None
        user = 'user_id' in msg and self.get_user(msg['user_id']) or None
        if msg['type'] == 'TextMessage':
            fwd_msg = "%s: %s" % (user['user']['name'], msg['body'])
        elif msg['type'] == 'LeaveMessage':
            fwd_msg = "- %s has left the room" % user['user']['name']
        elif msg['type'] == 'EnterMessage':
            fwd_msg = "- %s has entered the room" % user['user']['name']
        elif msg['type'] == 'PasteMessage':
            fwd_msg = "- %s pasted:\n%s" % (user['user']['name'], msg['body'])
        elif msg['type'] == 'UploadMessage':
            fwd_msg = "- %s uploaded %s" % (user['user']['name'], msg['body'])
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
        if '\n' in msg:
            self.room.paste(msg)
        else:
            self.room.speak(msg)


class CampfireStreamProtocol(basic.LineReceiver):
    delimiter = "\r\n"

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
        if self.status_size is not None:
            data, extra = data[:self.status_size], data[self.status_size:]
            self.status_size -= len(data)
        else:
            extra = ""

        self.status_data += data
        if self.status_size == 0:
            try:
                # ignore newline keep-alive
                msg = _json.loads(self.status_data)
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

    def __init__(self, consumer):
        if isinstance(consumer, CampfireBot):
            self.consumer = consumer
        else:
            raise TypeError("consumer should be an instance of CampfireBot")
    
    def startFactory(self):
        self.consumer.room.join()
        # generate the HTTP headers
        auth = base64.encodestring("%s:x" % self.consumer.auth_token).strip()
        header = [
            "GET /room/%d/live.json HTTP/1.1" % self.consumer.room.id,
            "Authorization: Basic %s" % auth,
            "User-Agent: pamper",
            "Host: streaming.campfirenow.com",
        ]
        self.header = "\r\n".join(header) + "\r\n\r\n"
    
    def stopFactory(self):
        if self.consumer.room:
            self.consumer.room.leave()
