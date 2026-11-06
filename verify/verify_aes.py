def xtime(b):
    b<<=1
    return (b^0x1b)&0xff if b&0x100 else b
def gmul(a,b):
    p=0
    for _ in range(8):
        if b&1: p^=a
        a=xtime(a); b>>=1
    return p
def inv(a):
    if a==0: return 0
    for x in range(1,256):
        if gmul(a,x)==1: return x
    raise ValueError
def rotl8(x,n):
    return ((x<<n)|(x>>(8-n)))&0xff
def gen_sbox():
    s=[0]*256
    for a in range(256):
        b=inv(a)
        s[a]= b ^ rotl8(b,1) ^ rotl8(b,2) ^ rotl8(b,3) ^ rotl8(b,4) ^ 0x63
    return s
S=gen_sbox()
print(hex(S[0x00]),hex(S[0x01]),hex(S[0x53]),hex(S[0x19]),hex(S[0xed]))
assert S[0x00]==0x63 and S[0x01]==0x7c and S[0x53]==0xed and S[0x19]==0xd4
INV=[0]*256
for i,v in enumerate(S): INV[v]=i
assert INV[0xd4]==0x19
def expand(key,nk,nr):
    w=[list(key[4*i:4*i+4]) for i in range(nk)]
    rcon=1
    for i in range(nk,4*(nr+1)):
        t=list(w[i-1])
        if i%nk==0:
            t=t[1:]+t[:1]
            t=[S[b] for b in t]
            t[0]^=rcon
            rcon=xtime(rcon)
        elif nk>6 and i%nk==4:
            t=[S[b] for b in t]
        w.append([a^b for a,b in zip(w[i-nk],t)])
    return w
def encrypt(block,key,nk,nr):
    st=[list(block[4*c:4*c+4]) for c in range(4)]
    w=expand(key,nk,nr)
    def ark(rnd):
        for c in range(4):
            for r_ in range(4): st[c][r_]^=w[4*rnd+c][r_]
    ark(0)
    for rnd in range(1,nr+1):
        for c in range(4):
            for r_ in range(4): st[c][r_]=S[st[c][r_]]
        for r_ in range(1,4):
            col=[st[c][r_] for c in range(4)]
            col=col[r_:]+col[:r_]
            for c in range(4): st[c][r_]=col[c]
        if rnd!=nr:
            for c in range(4):
                a=[st[c][i] for i in range(4)]
                st[c]=[gmul(a[0],2)^gmul(a[1],3)^a[2]^a[3],
                       a[0]^gmul(a[1],2)^gmul(a[2],3)^a[3],
                       a[0]^a[1]^gmul(a[2],2)^gmul(a[3],3),
                       gmul(a[0],3)^a[1]^a[2]^gmul(a[3],2)]
        ark(rnd)
    return bytes(st[c][r_] for c in range(4) for r_ in range(4))
cases=[
 (128,'2b7e151628aed2a6abf7158809cf4f3c','3243f6a8885a308d313198a2e0370734','3925841d02dc09fbdc118597196a0b32'),
 (128,'00000000000000000000000000000000','00000000000000000000000000000000','66e94bd4ef8a2c3b884cfa59ca342b2e'),
 (192,'000102030405060708090a0b0c0d0e0f1011121314151617','00112233445566778899aabbccddeeff','dda97ca4864cdfe06eaf70a0ec0d7191'),
 (256,'000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f','00112233445566778899aabbccddeeff','8ea2b7ca516745bfeafc49904b496089'),
]
for bits,k,p,exp in cases:
    nk=bits//32; nr={128:10,192:12,256:14}[bits]
    got=encrypt(bytes.fromhex(p),bytes.fromhex(k),nk,nr).hex()
    print(bits, got, 'OK' if got==exp else 'FAIL exp '+exp, 'steps=',1+(nr-1)*4+3)
