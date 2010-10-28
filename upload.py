import os
import sys

import yaml
from pinder import Campfire

# load configuration
config = yaml.load(open('config.yaml', 'r'))

campfire = Campfire(config['campfire']['domain'],
                    config['campfire']['token'], 
                    config['campfire']['ssl'])
room = campfire.find_room_by_name(config['campfire']['room'])

url = "%s/room/%d/uploads.xml" % (campfire.uri.geturl(), room.id)

for filename in sys.argv[1:]:
    x = (config['campfire']['token'], filename, url)
    os.system('curl -X POST -u %s:X -F "upload=@%s" %s -o /dev/null -#' % x)
