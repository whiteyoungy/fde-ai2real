#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""文风重排校验：确认只动了断句，没动内容。
用法：  python3 tools/prose_check.py <file.md>            # 只看可读性指标
       python3 tools/prose_check.py <file.md> --vs HEAD  # 与 git HEAD 版对比不变量
"""
import io,re,sys,subprocess,collections

def sentences(t):
    i=t.find('## 参考来源'); t=t[:i] if i>0 else t
    t=re.sub(r'```.*?```','',t,flags=re.S)
    out=[]
    for line in t.split('\n'):
        l=line.strip()
        if not l or l.startswith(('#','|','>','!','---')): continue
        l=re.sub(r'`[^`]*`','',l); l=re.sub(r'https?://\S+','',l)
        l=re.sub(r'^[-*]\s*(\[[ x]\]\s*)?','',l); l=re.sub(r'^\d+\.\s*','',l)
        for s in re.split(r'[。！？]',l):
            n=len(re.findall(r'[一-鿿]',s))
            if n>=4: out.append(n)
    return out

def invariants(t):
    """内容指纹。重排断句不应改变其中任何一项。"""
    return {
      '角标[N]': collections.Counter(re.findall(r'\[\d+\]',t)),
      'URL':     collections.Counter(re.findall(r'https?://[^\s)>\]]+',t)),
      '标题':    [l.strip() for l in t.split('\n') if l.startswith('#')],
      '数字':    collections.Counter(re.findall(r'\d+(?:\.\d+)?%?',t)),
      '代码块':  re.findall(r'```.*?```',t,flags=re.S),
      '英文词':  collections.Counter(re.findall(r'[A-Za-z][A-Za-z0-9_\-\.]{2,}',t)),
      '中文字数': len(re.findall(r'[一-鿿]',t)),
    }

def quotes_ok(t):
    s=re.sub(r'`[^`\n]*`','',re.sub(r'```.*?```','',t,flags=re.S))
    d=0
    for ch in s:
        if ch=='“':
            d+=1
            if d>1: return False
        elif ch=='”':
            d-=1
            if d<0: return False
    return d==0

def report(p):
    t=io.open(p,encoding='utf-8').read()
    S=sentences(t); S.sort()
    l60=sum(1 for x in S if x>60)/len(S)*100
    l100=sum(1 for x in S if x>100)/len(S)*100
    print('%s\n  句数 %d  均长 %.1f  P90 %d  最长 %d'%(p,len(S),sum(S)/len(S),S[int(len(S)*.9)],S[-1]))
    print('  >60字 %.1f%%   >100字 %.1f%%   引号配对 %s'%(l60,l100,'OK' if quotes_ok(t) else '**坏了**'))
    return l60

def diff(p,ref):
    """ref 可以是 git 引用（如 HEAD），也可以是一个基线文件的路径。"""
    import os
    new=io.open(p,encoding='utf-8').read()
    if os.path.isfile(ref):
        old=io.open(ref,encoding='utf-8').read()
    else:
        old=subprocess.run(['git','show',f'{ref}:{p}'],capture_output=True,text=True).stdout
    if not old: print('  （找不到基线版本，跳过对比）'); return True
    a,b=invariants(old),invariants(new)
    ok=True
    for k in a:
        if k=='中文字数':
            d=(b[k]-a[k])/a[k]*100
            flag = abs(d)<=6
            print('  %-8s %d -> %d  (%+.1f%%) %s'%(k,a[k],b[k],d,'OK' if flag else '**超出 ±6%**'))
            ok&=flag; continue
        if a[k]!=b[k]:
            ok=False
            if isinstance(a[k],collections.Counter):
                lost=a[k]-b[k]; add=b[k]-a[k]
                print('  %-8s **变了**  丢失=%s  新增=%s'%(k,dict(list(lost.items())[:8]),dict(list(add.items())[:8])))
            else:
                sa,sb=set(map(str,a[k])),set(map(str,b[k]))
                print('  %-8s **变了**  丢失=%s  新增=%s'%(k,list(sa-sb)[:5],list(sb-sa)[:5]))
        else:
            print('  %-8s 一致'%k)
    return ok

if __name__=='__main__':
    f=sys.argv[1]; report(f)
    if '--vs' in sys.argv:
        ref=sys.argv[sys.argv.index('--vs')+1]
        print('  —— 内容不变量对比（vs %s）——'%ref)
        ok=diff(f,ref)
        print('  结论：%s'%('通过' if ok else '**有内容被改动，需人工确认**'))
        sys.exit(0 if ok else 1)
