from __future__ import print_function
from web3 import Web3, KeepAliveRPCProvider, IPCProvider
import subprocess, signal
import time
import sys
import os
from values import MyGlobals

    



def start_private_chain(chain,etherbase,debug=False):#构建私人区块链

    devnull = open(os.devnull, 'w')#在不同的系统上null设备的路径，在Windows下为‘nul’，在POSIX下为‘/dev/null’


    if chain!= 'remptychain':

        # Remove previous blockchain
        pr=subprocess.Popen(['rm','-rf','./blockchains/'+chain])#用命令行执行程序删除区块链
        pr.wait()#

        # Init new blockchain
        if debug: pr=subprocess.Popen(['geth','--datadir','./blockchains/'+chain,'init','./blockchains/genesis.json'])#创建一个go实现的区块链
        else: pr=subprocess.Popen(['geth','--datadir','./blockchains/'+chain,'init','./blockchains/genesis.json'],stdout=devnull, stderr=devnull)
        pr.wait()

        # Copy the accounts
        pr=subprocess.Popen(['cp','-r','./blockchains/remptychain/keystore','./blockchains/'+chain+'/'])#复制创建好的区块链文件夹
        pr.wait()



    if Web3(KeepAliveRPCProvider(host='127.0.0.1', port=MyGlobals.port_number)).isConnected() :
            print('\033[91m[-] Some blockchain is active, killing it... \033[0m', end='')
            kill_active_blockchain()
            if not( Web3(KeepAliveRPCProvider(host='127.0.0.1', port=MyGlobals.port_number)).isConnected() ):#isConnected检查是否与节点连接上
                print('\033[92m Killed \033[0m')
            else:
                print('Cannot kill')
    
    print('\033[1m[ ] Connecting to PRIVATE blockchain %s  \033[0m' % chain, end='')
    if debug:#--rpccorsdomain value 接受跨源请求的域的逗号分隔列表
        pro = subprocess.Popen(['geth','--rpc','--rpccorsdomain','"*"','--rpcapi="db,eth,net,web3,personal,web3"', '--rpcport',MyGlobals.port_number, '--datadir','blockchains/'+chain,'--networkid','123','--mine','--minerthreads=1','--etherbase='+MyGlobals.etherbase_account])
    else:
        pro = subprocess.Popen(['geth','--rpc','--rpccorsdomain','"*"','--rpcapi="db,eth,net,web3,personal,web3"', '--rpcport',MyGlobals.port_number, '--datadir','blockchains/'+chain,'--networkid','123','--mine','--minerthreads=1','--etherbase='+MyGlobals.etherbase_account],stdout=devnull, stderr=devnull)

    global web3
    MyGlobals.web3 = Web3(KeepAliveRPCProvider(host='127.0.0.1', port=MyGlobals.port_number))
    while( not MyGlobals.web3.isConnected() ):
        print('',end='.')
        if MyGlobals.exec_as_script:
            sys.stdout.flush()        
        time.sleep(1)

    if( MyGlobals.web3.isConnected() ):
        print('\033[92m ESTABLISHED \033[0m')
    else:
        print('\033[93m[-] Connection failed. Exiting\033[0m')
        exit(2)
    
    return pro


def kill_active_blockchain():

    devnull = open(os.devnull, 'w')    
    p = subprocess.Popen(['fuser',MyGlobals.port_number+'/tcp'], stdout=subprocess.PIPE, stderr=devnull)
    out, err = p.communicate()
    for line in out.splitlines():
        pid = int(line.split(None, 1)[0])
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)

    devnull = open(os.devnull, 'w')    
    #p = subprocess.Popen(['lsof','+D','blockchains/','-t' ], stdout=subprocess.PIPE, stderr=devnull)
    p = subprocess.Popen(['lsof','-t','-i','tcp:'+MyGlobals.port_number ], stdout=subprocess.PIPE, stderr=devnull)
    out, err = p.communicate()
    for line in out.splitlines():
        pid = int(line.split(None, 1)[0])
        p2 = subprocess.Popen(['ps','-p',str(pid) ], stdout=subprocess.PIPE, stderr=devnull)
        out2,err2 = p2.communicate()
        if bytes.decode(out2).find('datadir') >= 0:
            os.kill(pid, signal.SIGKILL)
        time.sleep(1)


def execute_transactions(txs):


    count = 0
    weiused = 0
    for tx in txs:
        MyGlobals.web3.personal.unlockAccount(tx['from'],'1',15000)#当进行发送交易时, 需要先对转出的账户进行解锁操作
        try:#unlockAccount(address, password, unlockDuraction [, callback])
            hash = MyGlobals.web3.eth.sendTransaction( tx )#发送给tx

            while MyGlobals.web3.eth.getTransaction(hash)['blockNumber'] is None:#getTransaction找对应交易哈希值的交易
                print('.',end='')
                if MyGlobals.exec_as_script:
                    sys.stdout.flush()
                time.sleep(1)
            print(' tx[%d] mined ' % count, end='')

            weiused += MyGlobals.web3.eth.getTransactionReceipt(hash)['gasUsed'] * MyGlobals.web3.eth.getTransaction(hash)['gasPrice']

        except Exception as e:
            print ("Exception: "+str(e))

        count +=1#区块中的交易数+1

    return weiused#返还剩余的gas






