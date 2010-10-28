from wokkel.xmppim import MessageProtocol, AvailablePresence
from twisted.words.xish import domish

class JabberBot(MessageProtocol):
    """A really simple XMPP client that passes incoming messages to the
    campfire bot and sends messages passed to it by the campfire bot.
    
    """
    def __init__(self, forward_to):
        self.campfire = None
        self.forward_to = forward_to
        
    def connectionMade(self):
        print "Connected!"
        # send initial presence
        self.send(AvailablePresence())

    def connectionLost(self, reason):
        print "Disconnected!"

    def onMessage(self, msg):
        print msg['from']
        if msg["type"] == 'chat' and hasattr(msg, "body") and msg.body and \
           msg['from'].startswith(self.forward_to) and self.campfire:
            self.campfire.forwardMessage(unicode(msg.body))
    
    def forwardMessage(self, body):
        msg = domish.Element((None, "message"))
        msg["to"] = self.forward_to
        msg["type"] = 'chat'
        msg.addElement("body", content=body)
        self.send(msg)
