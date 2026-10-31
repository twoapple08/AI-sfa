import sys,cv2,numpy as np
S,sh,out=sys.argv[1:4]; idx=[int(x) for x in sys.argv[4].split(',')]; cols=int(sys.argv[5]) if len(sys.argv)>5 else 4
W,H=480,270; cells=[]
for i in idx:
    f=cv2.resize(cv2.imread(f'{S}/fr/{sh}/{i:03d}.png'),(W,H),interpolation=cv2.INTER_AREA)
    f=cv2.copyMakeBorder(f,22,2,2,2,cv2.BORDER_CONSTANT,value=(30,30,30))
    cv2.putText(f,f'{sh} {i}',(6,17),0,0.6,(0,255,255),1,cv2.LINE_AA); cells.append(f)
while len(cells)%cols: cells.append(np.zeros_like(cells[0]))
cv2.imwrite(out,np.vstack([np.hstack(cells[j:j+cols]) for j in range(0,len(cells),cols)]),[cv2.IMWRITE_JPEG_QUALITY,88])
