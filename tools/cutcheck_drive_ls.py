import re,sys,subprocess
def ls(fid):
    h=subprocess.run(['curl','-sSL',f'https://drive.google.com/embeddedfolderview?id={fid}'],capture_output=True,text=True).stdout
    return re.findall(r'href="https://drive.google.com/(?:drive/folders|file/d)/([^/"?]+)[^>]*>.*?flip-entry-title">([^<]+)<',h,re.S)
if __name__=='__main__':
    for i,n in ls(sys.argv[1]): print(i,n)
