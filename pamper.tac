from twisted.application import service
from twisted.application.internet import TCPClient
from twisted.words.protocols.jabber import jid
from wokkel.client import XMPPClient
import yaml

from campfire import CampfireBot, CampfireStreamFactory
from jabber import JabberBot

# load configuration
config = yaml.load(open('config.yaml', 'r'))

application = service.Application("pamper")

# setup the xmpp bot
xmppClient = XMPPClient(jid.internJID("%s/pamper" % config['jabber']['user']),
                        config['jabber']['pass'])
xmppClient.logTraffic = False
jabberBot = JabberBot(config['deliver_to'])
jabberBot.setHandlerParent(xmppClient)
xmppClient.setServiceParent(application)

# setup the campfire bot
campfireBot = CampfireBot(config['campfire']['domain'], 
                          config['campfire']['room'], 
                          config['campfire']['token'],
                          config['campfire']['ssl'])
campfireClientService = TCPClient("streaming.campfirenow.com", 
                                  config['campfire']['ssl'] and 443 or 80, 
                                  CampfireStreamFactory(campfireBot))
campfireClientService.setServiceParent(application)

# point the bots at each other
jabberBot.campfire = campfireBot
campfireBot.xmpp = jabberBot
