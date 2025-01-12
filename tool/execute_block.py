from __future__ import print_function
import os
import sys
import re
from execute_instruction import *
from values import get_params, initialize_params, print_params
from values import MyGlobals, clear_globals
from misc import *



def execute_one_block( ops , stack , pos , trace, storage, mmemory, data, configurations, search_op, search_function, jumpdepth, calldepth, debug, read_from_blockchain):



    global s, stop_search, search_condition_found, visited_nodes#为了使用MyGlobals的类变量

    if MyGlobals.stop_search : return 

    MyGlobals.visited_nodes += 1#搜索一个契约的所有路径总数
    if MyGlobals.visited_nodes > MyGlobals.MAX_VISITED_NODES: return
    
    
    # Execute the next block of operations 执行操作的新块
    first = True
    newpos = pos
    while (first or newpos != pos) and not MyGlobals.stop_search:#直到停止搜索
    #first or newpos != pos：基本块的入口

        first = False
        pos = newpos#pc所指的指令位置    
            
        # If no more code, then stop
        if pos >= len(ops) or pos < 0:
            if debug: print('\033[94m[+] Reached bad/end of execution\033[0m')#字节码分析执行结束
            return False


        # Debug info
        if debug: print('[ %3d %3d %5d] : %4x : %12s : %s  ' % (calldepth, jumpdepth, MyGlobals.visited_nodes, ops[pos]['id'], ops[pos]['o'], ops[pos]['input']) )


        # Check if calldepth or jumpdepth should be changed 检查calldepth和jumpdepth是否要修改
        # and stop the search if certain conditions are met 停止条件
        if pos == 0: #第一条指令
            calldepth += 1
            jumpdepth = 0
        if ops[pos]['o'] == 'JUMPDEST': jumpdepth += 1#该位置是JUMPDEST指令则调用深度+1,jumpdepth是CFG控制流图中的路径长度
        if( jumpdepth > MyGlobals.MAX_JUMP_DEPTH): #保证调用深度不超过MAX_JUMP_DEPTH
            if debug:print ('\033[95m[-] Reach MAX_JUMP_DEPTH\033[0m' )
            return
        if( calldepth > MyGlobals.MAX_CALL_DEPTH): 
            if debug:print ('\033[95m[-] Reach MAX_CALL_DEPTH\033[0m' )
            return




        # Check if configuration exist if 
        # - it is the first instruction in the code (the code restarted)第一条指令
        # - it is jumpdest JUMPDEST表明这个Block是一个跳转的起始位置
        # - it is the first instruction after JUMPI 条件跳转语句后面第一条指令是基本块的入口
        if pos == 0 or ops[pos]['o'] == 'JUMPDEST' or (pos > 0 and ops[pos-1]['o'] == 'JUMPI'):
            if seen_configuration( configurations, ops, pos, stack, mmemory, storage): #如果有配置则可以debug，否则添加默认配置
                if debug:print ('\033[95m[-] Seen configuration\033[0m' )
                return
        
    

        # Check if the current op is one of the search ops判断当前的操作是否是搜索的操作之一
        if ops[pos]['o'] in search_op:

            if debug:
                print('\033[96m[+] Reached %s at %x \033[0m'  % (ops[pos]['o'], ops[pos]['id'] ) )
                print_stack( stack )
        #search_function是类似ether_lock_can_recieve,ether_lock_can_send，ether_suicide，ether_leak函数的函数变量，可以传入参数，相当于调用该函数
        #ether_lock_can_recieve函数# Once STOP/RETURN  is executed, the search can be stoppped
        #ether_lock_can_send# Once STOP/RETURN  is executed, the search can be stoppped
        #ether_suicide# Once SUICIDE is executed, the contract is killed
        #Thus the search is stoppped and the contract is flagged as suicidal
        #ether_leak# Once SUICIDE is executed, then no need to look for the final STOP or RETURN
        #because SUICIDE is already a stopping instruction
            new_search_condition_found, stop_expanding_the_search_tree =  search_function( ops[pos]['o'] , stack , trace, debug )
            MyGlobals.search_condition_found = MyGlobals.search_condition_found or new_search_condition_found#是否找到search_condition

            if stop_expanding_the_search_tree:#如果停止生成搜索树则返回函数调用追踪的参数
                get_function_calls( calldepth, debug )


            if MyGlobals.stop_search or stop_expanding_the_search_tree:  return


        # Execute the next operation该基本块中的下一条指令，更新pc的值
        newpos, halt = execute( ops, stack, pos, storage, mmemory, data, trace, calldepth, debug, read_from_blockchain  )


        # If halt is True, then the execution should stop 
        if halt:
        
            if debug: print('\033[94m[+] Halted on %s on line %x \033[0m' % (ops[pos]['o'],ops[pos]['id']))
            
            # If normal stop 正常的程序结束
            if ops[pos]['o'] in ['STOP','RETURN','SUICIDE']:

                # If search condition still not found then call again the contract
                # (infinite loop is prevented by calldepth )
                if not MyGlobals.search_condition_found:#还未找到搜索条件则再次调用该合约
                    stack   = []
                    mmemory = {}
                    newpos = 0
                    #data = {}

                    if not debug:
                        print('%d' % calldepth,end='')
                        if MyGlobals.exec_as_script:
                            sys.stdout.flush()#清空标准输出设备
                    continue

                # Else stop the search否则（如果找到了）停止搜索
                else:

                    MyGlobals.stop_search = True
                    get_function_calls( calldepth, debug )


                    return


            # In all other cases stop further search in this branch of the tree在所有其他情况（非正常结束程序）下，停止在树的这个分支的进一步搜索
            else:
                return 
    
        # If program counter did not move 
        # It means either:
        # 1) we need to branch
        # 2) calldataload
        # 3) calldatasize
        # 4) unknown instruction
        if pos == newpos:#pc不增加的四种情况
        
            si = ops[pos]

            # It can be JUMPI
            if si['o'] == 'JUMPI':#分支
            
                if len(stack) < 2:
                    if debug: print('\033[95m[-] In JUMPI (line %x) the stack is too small to execute JUMPI\033[0m' % pos )
                    return False
        
                addr = stack.pop()#第一个弹出的参数是地址
                des = stack.pop()#判断条件

                if is_undefined(des):#表达式不能被求值
                    if debug: print('\033[95m[-] In JUMPI the expression cannot be evaluated (is undefined)\033[0m'   )
                    return False

                sole = '  * sole * '


                #
                # Branch when decision is incorrect (no need to compute the addresses)  决定不正确时（不需要计算地址）则分支    
                #

                # In the fast search mode, the jumpi pos + 1 must be in the list of good jump positions
                if is_good_jump( ops, pos+1, debug ):#如果不是调试模式 

                    MyGlobals.s.push()#把下面的断言压入栈
                    MyGlobals.s.add( des['z3'] == 0)#添加限制到z3 solver
                    try:

                        if MyGlobals.s.check() == sat:#如果可解，如果没有目标地址则继续深搜


                            storage2 = copy.deepcopy(storage)
                            stack2 = copy.deepcopy(stack)
                            trace2 = copy.deepcopy(trace)
                            mmemory2 = copy.deepcopy(mmemory)
                            data2 = copy.deepcopy(data)#深拷贝各个存储区

                            if debug: print('\t'*8+'-'*20+'JUMPI branch 1 (go through)')
                            sole = ''
                            #用深拷贝的存储区执行
                            execute_one_block(ops,stack2,   pos + 1,    trace2, storage2,   mmemory2, data2, configurations,    search_op, search_function, jumpdepth+1, calldepth, debug, read_from_blockchain )
                            #每执行一个块则jumpdepth+1

                    except Exception as e:
                        print ("Exception: "+str(e))

                    MyGlobals.s.pop()#删除和push之间的限制条件，弹出断言


                if MyGlobals.stop_search: return

                #
                # Branch when the decision is possibly correct 
                #
                if not is_fixed(addr):#如果跳转地址不是定值是变量则不跳转
                    if debug: print('\033[95m[-] In JUMPI the jump address cannot be determined \033[0m'  % jump_dest )
                    return False
    
                jump_dest = get_value( addr )#如果跳转地址是定值，取得跳转地址
                if( jump_dest <= 0):#如果跳转地址无效则不跳转
                    if debug: print('\033[95m[-] The jump destination is not a valid address : %x\033[0m'  % jump_dest )
                    return False

                new_position= find_pos(ops, jump_dest )#找JUMPDEST指令的地址
                if( new_position < 0):#如果找不到就不跳转
                    if debug: print('\033[95m[-] The code has no such jump destination: %s at line %x\033[0m' % (hex(jump_dest), si['id']) )
                    return False


                # In the fast search mode, the jumpi new_position must be in the list of good jump positions
                if is_good_jump( ops, new_position, debug ): #如果不是debug模式

                    MyGlobals.s.push()
                    MyGlobals.s.add( des['z3'] != 0)
                    
                    try:
                        if MyGlobals.s.check() == sat:

                            if debug:
                                if ops[pos]['id'] -  MyGlobals.last_eq_step < 5:
                                    print('\t'*8+'-'*18+'\033[96m %2d Executing function %x \033[0m' % (calldepth, MyGlobals.last_eq_func) )


                            storage2 = copy.deepcopy(storage)
                            stack2 = copy.deepcopy(stack)
                            trace2 = copy.deepcopy(trace)
                            mmemory2 = copy.deepcopy(mmemory)
                            data2 = copy.deepcopy(data)

                            if debug: print( ('\t'*8+'-'*20+'JUMPI branch 2 (jump) on step %x' + sole ) % ops[pos]['id'] )

                            execute_one_block(ops,stack2,   new_position,   trace2, storage2,   mmemory2, data2, configurations,    search_op, search_function,  jumpdepth, calldepth, debug, read_from_blockchain )


                    except Exception as e:
                        print ("Exception: "+str(e))

                    MyGlobals.s.pop()
                
                return 

            # It can be CALLDATALOAD汇编指令CALLDATALOAD
            elif si['o'] == 'CALLDATALOAD':

                addr = stack.pop()#地址

                # First find the symbolic variable name 先找符号变量名
                text = str(addr['z3'])
                regex = re.compile('input[0-9]*\[[0-9 ]*\]')
                match = re.search( regex, text)#用正则表达式寻找起止坐标
                if match:
                    sm = text[match.start():match.end()]#获得

                    # assign random (offset) address as value for the variable 
                    random_address = get_hash(sm) >> 64
                    
                    r2 = re.compile('\[[0-9 ]*\]')
                    indmat = re.search( r2, sm )
                    index = -2
                    if indmat:
                        index = int( sm[indmat.start()+1:indmat.end()-1] )

                    total_added_to_solver = 0

                    # add 'd' at the end of the name of the symbolic variable (used later to distinguish them)
                    if index>= 0 and ('data-'+str(calldepth)+'-'+str(index)) in data:
                        data[('data-'+str(calldepth)+'-'+str(index))] = BitVec(sm+'d',256)
                        MyGlobals.s.push()
                        MyGlobals.s.add( data[('data-'+str(calldepth)+'-'+str(index))] == random_address  )
                        total_added_to_solver = 1


                    # replace the variable with concrete value in stack and memory
                    for st in stack:
                        if 'z3' in st:
                            st['z3'] = simplify(substitute( st['z3'], (BitVec(sm,256),BitVecVal(random_address, 256))))
                    for st in mmemory:
                        if 'z3' in mmemory[st]:
                            mmemory[st]['z3'] = simplify(substitute( mmemory[st]['z3'], (BitVec(sm,256),BitVecVal(random_address, 256))))

                    # replace in the address as well
                    addr = simplify(substitute(addr['z3'], (BitVec(sm,256),BitVecVal(random_address, 256)) ) )

                    # Branch
                    branch_array_size = [0,1,2]
                    for one_branch_size in branch_array_size:

                        storage2 = copy.deepcopy(storage)
                        stack2 = copy.deepcopy(stack)
                        trace2 = copy.deepcopy(trace)
                        mmemory2 = copy.deepcopy(mmemory)
                        data2 = copy.deepcopy(data)

                        data2['data-'+str(calldepth)+'-' + str(addr)] = BitVecVal(one_branch_size,256)
                        for i in range(one_branch_size):
                            data2['data-'+str(calldepth)+'-'+ str(addr.as_long()+32+32*i)] = BitVec('input'+str(calldepth)+'['+('%s'%(addr.as_long()+32+32*i))+']',256)

                        stack2.append( {'type':'constant','step':ops[pos]['id'], 'z3':BitVecVal( one_branch_size, 256)})

                        MyGlobals.s.push()
                        MyGlobals.s.add( BitVec('input'+str(calldepth)+('[%x'%addr.as_long())+']',256) == one_branch_size)

                        execute_one_block(ops,stack2,   pos+1,  trace2, storage2,   mmemory2, data2, configurations,    search_op, search_function,  jumpdepth, calldepth, debug, read_from_blockchain )

                        MyGlobals.s.pop()


                    for ta in range(total_added_to_solver):
                        MyGlobals.s.pop()


                else:
                    if debug: 
                        print('\033[95m[-] In CALLDATALOAD the address does not contain symbolic variable input[*]\033[0m' )
                        print( addr )
                    return 

                return


            # It can be CALLDATASIZE汇编指令CALLDATASIZE
            elif si['o'] == 'CALLDATASIZE':


                    # Assume it is SYMBOLIC variable
                    storage2 = copy.deepcopy(storage)
                    stack2 = copy.deepcopy(stack)
                    trace2 = copy.deepcopy(trace)
                    mmemory2 = copy.deepcopy(mmemory)
                    data2 = copy.deepcopy(data)

                    if -1 not in data2:
                        data2['inputlength-'+str(calldepth)] = BitVec('inputlength-'+str(calldepth), 256)
                    stack2.append( {'type':'constant','step':ops[pos]['id'], 'z3': data2['inputlength-'+str(calldepth)]} )#step指令在字节码中的序号,存入data的大小
                    execute_one_block(ops,stack2,   pos+1,  trace2, storage2,   mmemory2, data2, configurations,    search_op, search_function,  jumpdepth, calldepth, debug, read_from_blockchain )

                    
                    # or Branch on 4 different FIXED sizes
                    branch_array_size = [0,8,8+1*32,8+2*32]
                    for one_branch_size in branch_array_size:

                        storage2 = copy.deepcopy(storage)
                        stack2 = copy.deepcopy(stack)
                        trace2 = copy.deepcopy(trace)
                        mmemory2 = copy.deepcopy(mmemory)
                        data2 = copy.deepcopy(data)
                        
                        stack2.append( {'type':'constant','step':ops[pos]['id'], 'z3': BitVecVal(one_branch_size,256)} )

                        execute_one_block(ops,stack2,   pos+1,  trace2, storage2,   mmemory2, data2, configurations,    search_op, search_function,  jumpdepth, calldepth, debug, read_from_blockchain )
                    

                    return 




            # If nothing from above then stop
            else:
                print('\033[95m[-] Unknown %s on line %x \033[0m' % (si['o'],ops[pos]['id']) )
                return 











