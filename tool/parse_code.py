from instruction_list import *

def print_code(code,ops):
    for o in ops:
        print('%6x  : %4d : %2s : %12s : %s' % (o['id'],o['id'], o['op'],o['o'] , o['input']) )
    print('Total byte/code size: %d %d' % (len(code)/2,len(ops)) )

def get_one_op( code, pos, size_of_input, debug=False ):#pos是parse_code解析到的字节码下标，pos+2是当前解析的汇编指令下标，size_of_input是汇编指令PUSHX中的X的具体值，字节码中X是占据两位十六进制位，要*2
    if pos + 2 + size_of_input > len(code ):
        if debug: print('Incorrect code op at %x : %d : %d :  %s' % (pos/2, pos+2+size_of_input, len(code), code[pos:] ) )
    instruction = '0x' + code[pos:pos+2]
    o = ''
    if instruction in cops:#cops：十六进制和汇编指令的字典
        o = cops[ instruction ]#将十六进制转换为汇编指令
    t = {'id':int(pos/2),'op':code[pos:pos+2],'input':code[pos+2:pos+2+2*size_of_input],'o':o}#构建字典，汇编指令的下标，操作码的值，PUSH要处理的字节码开始下标，汇编指令
    return (pos + 2 + 2*size_of_input, t)#t是汇编指令对象，包含汇编指令的各个参数

def parse_code( code, debug = False):#传入字节码code
    ops = list()

    i = 0;
    while i < len(code):

        op = code[i:i+2]#每两位取一个操作码的十六进制值

        if op >= '60' and op <='7f':#push的字节码值范围
            i, t = get_one_op( code, i, int(op,16) - int('60',16)+1, debug )#int('60',16)将十六进制的60转换为十进制的整数，将全部的字节码code传给get_one_op函数
            ops.append(t)#加入汇编指令对象列表
        else:
            i, t = get_one_op( code, i, 0, debug );
            ops.append(t)

    return ops

def code_has_instruction( code, ops):#ops传入类似['SUICIDE']的数组，判断数组中的指令是否在字节码的汇编指令中出现过

    for o in code: #o['o']获得字节码中的汇编指令字符串
        if o['o'] in ops:
            return True

    return False


def get_dictionary_of_ops( ops ):#
    d = {}
    for t in ops:
        if t['op'] not in d: d[ t['op'] ] = True
    return d

def has_call( ops ):
    for t in ops:
        if t['op'] == 'f1': return True
    return False

def find_pos( code, byte_position):#code传入ops（汇编指令对象列表）
    found = -1
    for i in range(len(code)) :
        if code[i]['id'] == byte_position:#线性判断在byte_position位置是否有汇编指令JUMPDEST
            found = i
    if found >= 0 and code[found]['o'] == 'JUMPDEST':#返回查找到的JUMPDEST汇编指令的位置下标
        return found

    return -1

