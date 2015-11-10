from os import listdir
from os.path import isfile, join
import heapq
f = []
mypath = r"C:\Users\Ace\Google Drive\AceBots\AcePictureBot\Code2\images\waifu\\"
folders = listdir(mypath)
max_num = []
fol = []
for folder in folders:
    onlyfiles = [f for f in listdir(join(mypath, folder)) if isfile(join(mypath, folder, f))]
    max_num.append(len(onlyfiles))
    fol.append(folder)

top_three = heapq.nlargest(3, max_num)
print("Top Three:")
print(top_three)
for a in top_three:
    print(fol[max_num.index(a)])
