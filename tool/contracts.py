from __future__ import print_function
from web3 import Web3, KeepAliveRPCProvider, IPCProvider
import os.path
import json
import sched, time
import sys
import glob
import sys
import json
import rlp
from rlp.utils import decode_hex, encode_hex, ascii_chr, str_to_bytes
from subprocess import Popen, PIPE, STDOUT
from values import MyGlobals
from blockchain import *

def compile_contract(filename):

    print('\033[1m[ ] Compiling Solidity contract from the file %s ... \033[0m' % filename, end='')

    source_file = filename
    if (not os.path.isfile(source_file) ):
        print('\033[91m[-] Contract file %s does NOT exist\033[0m' % source_file )
        return

    with open(filename, 'r') as myfile:
        code=myfile.read()
    
    p=Popen(['solc','--bin','--abi','-o','out',source_file,'--overwrite'], stdout=PIPE, stdin=PIPE, stderr=STDOUT)#将所有的输出都保存到一个单独的文件夹中，使用abi生成bytes输出,用源文件的名字命名abi文件
    solo = ''
    while p.poll() is None:#检查子进程是否已终止。 设置并返回返回码属性。如果还在运行，返回 None。
        l = p.stdout.readline()#使用标准输出设备读取子进程的实时输出结果
        solo += bytes.decode(l)#以指定的编码格式解码 bytes 对象。默认编码为 'utf-8'
    if 'Error' in solo:
        print(solo)
        print('\033[91m[-] Cannot compile the contract \033[0m')
        exit()
    p.wait()

    print('\033[92m Done \033[0m')


def get_function_hashes(contract):#获得函数的哈希值

        
    data = json.load(open('out/'+contract+'.abi'))#
    fhashes = {}
    for d in data:
        if 'type' in d and d['type'] == 'function':
            hs = ''
            if 'name' in d: hs = d['name']
            fr = True
            hs += '('
            if 'inputs' in d:
                for i in d['inputs']:
                    if not fr: hs +=','
                    hs += i['type']
                    fr = False
            hs += ')'
            hash_op = Web3.sha3(hs.encode('utf-8'), encoding='bytes')

            fhashes[hash_op[2:10]] = hs

    return fhashes



def deploy_contract(filename, etherbase, rawcode = False):

    if rawcode:
        with open(filename, 'r') as myfile: byt=myfile.read()
        filename_write_address = os.path.basename(filename)+'.address'
        
    else:
        filename_abi = os.path.basename(filename)+'.abi'
        filename_bin = os.path.basename(filename)+'.bin'
        filename_write_address = os.path.basename(filename)+'.address'
        with open('./out/'+filename_abi, 'r') as myfile: abi=myfile.read()
        with open('./out/'+filename_bin, 'r') as myfile: byt=myfile.read()
        if( len(abi) == 0 or len(byt) == 0 ):
            print('\033[91m[-] Some of the files is missing or empty: |%s|=%d  |%s|=%d' % (filename_abi, len(abi), filename_bin, len(byt) ) )
            print('The contracts have NOT been deployed\033[0m')
            return

        abi = json.loads(abi)

    print('\033[1m[ ] Deploying contract \033[0m', end='')
    MyGlobals.web3.personal.unlockAccount(etherbase, '1', 15000)#address - String: 要解锁的账户地址。  password - String - 账户密码。  unlockDuration - Number - 将帐户保持在解锁状态的持续时间。


    try:#发送一个交易到网络，返回交易的哈希值
        transaction_creation_hash = MyGlobals.web3.eth.sendTransaction( {'from':etherbase, 'data': ('0x' if byt[0:2]!='0x' else '') +byt , 'gas':6000000} )#
    except Exception as e:
        print ("Exception: "+str(e))
        return None

    global s
    s = sched.scheduler(time.time, time.sleep)
    s.enter(1, 1, confirm_contract, (transaction_creation_hash,))#每隔一秒调用一次confirm_contract函数，后面是confirm_contract函数的参数
    s.run()#运行事件调度器
    print('\033[92m confirmed at address: %s \033[0m' % contract_address)
    fullcode = MyGlobals.web3.eth.getCode(contract_address)#给定地址合约编译后的字节代码
    print('\033[1m[ ] Contract code length on the blockchain : \033[0m \033[92m  %d  : %s... \033[0m' % (len(fullcode), fullcode[:30] ) )
    with open('./out/'+filename_write_address, 'w') as f:#写入合约字节码
        f.write(contract_address)
        f.close()
    print('\033[1m[ ] Contract address saved in file: \033[0m\033[92m%s \033[0m' % ('./out/'+filename_write_address))

    return contract_address


def confirm_contract(transaction_creation_hash):
    print('.', end="")
#    sys.stdout.flush()
    global contract_address#如果交易是一个合约创建的，请使用web3.eth.getTransactionReceipt()在交易完成后获取合约的地址。
    receipt = MyGlobals.web3.eth.getTransactionReceipt(transaction_creation_hash)#获得交易的收据对象，如果找不到返回null
    if( receipt is not None):#有收据
        contract_address = receipt['contractAddress']#记录收据和合约的映射关系
        return

    s.enter(1, 1, confirm_contract, (transaction_creation_hash,))

#下面三个函数负责rlp编码
def rlp_encode(input):
    if isinstance(input,str):
        if len(input) == 1 and ord(input) < 0x80: return input
        else: return encode_length(len(input), 0x80) + input
    elif isinstance(input,list):
        output = ''
        for item in input: output += rlp_encode(item)
        return encode_length(len(output), 0xc0) + output

def encode_length(L,offset):
    if L < 56:
         return chr(L + offset)
    elif L < 256**8:
         BL = to_binary(L)
         return chr(len(BL) + offset + 55) + BL
    else:
         raise Exception("input too long")

def to_binary(x):
    if x == 0:
        return ''
    else: 
        return to_binary(int(x / 256)) + chr(x % 256)    

def normalize_address(x, allow_blank=False):#x传入账户地址，将地址转换为合法地址
    if allow_blank and x == '':#允许空地址
        return ''
    if len(x) in (42, 50) and x[:2] == '0x':#如果前两个字符是0x，截取从第三个字符开始的所有字符串
        x = x[2:]
    if len(x) in (40, 48):
        x = decode_hex(x)
    if len(x) == 24:
        assert len(x) == 24 and sha3(x[:20])[:4] == x[-4:]#比较哈希值
        x = x[:20]
    if len(x) != 20:
        raise Exception("Invalid address format: %r" % x)
    return x
     

def predict_contract_address(accountAddress):

    nonce = int(MyGlobals.web3.eth.getTransactionCount(accountAddress)) #返回指定地址发起的交易数
    adr = Web3.sha3(rlp.encode([normalize_address(accountAddress), nonce]), encoding='bytes')[-40:]#
    return '0x'+adr



