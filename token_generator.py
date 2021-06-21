import random
import pickle
import sys
    
if(len(sys.argv) != 3):
    print("Usage: python {} TokenName NumTokens".format(sys.argv[0]))
    sys.exit(1)

f = open(sys.argv[1], "w")
tokenlist = []
for i in range(int(sys.argv[2])):
    h = random.getrandbits(128)
    h = "%032x" % h
    tokenlist.append(h + "\n")
f.writelines(tokenlist)
f.close()

