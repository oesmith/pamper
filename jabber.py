from wokkel.xmppim import MessageProtocol, AvailablePresence
from twisted.words.xish import domish

class JabberBot(MessageProtocol):
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
        if msg["type"] == 'chat' and hasattr(msg, "body") and msg.body and self.campfire:
            self.campfire.forwardMessage(str(msg.body))
    
    def forwardMessage(self, body):
        msg = domish.Element((None, "message"))
        msg["to"] = self.forward_to
        msg["type"] = 'chat'
        msg.addElement("body", content=body)
        self.send(msg)
