import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.mem.*;
import java.util.*;
import java.io.*;
public class AllStrRefs extends GhidraScript {
    public void run() throws Exception {
        Memory mem = currentProgram.getMemory(); Listing l = currentProgram.getListing(); FunctionManager fm = currentProgram.getFunctionManager();
        long lo = 0x2f0000L, hi = 0x392070L; byte[] buf = new byte[(int)(hi-lo)]; mem.getBytes(currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(lo), buf);
        // string start map (any printable run >=4 after a NUL) and a "inside string" map to its start
        Map<Long,String> starts = new HashMap<>(); long[] owner = new long[buf.length];
        for (int i = 1; i < buf.length - 4; i++) {
            if (buf[i-1] == 0 && buf[i] >= 0x09 && buf[i] < 0x7f) { int j = i; while (j < buf.length && buf[j] >= 0x09 && buf[j] < 0x7f) j++; if (j - i >= 4 && j < buf.length && buf[j] == 0) { starts.put(lo + i, new String(buf, i, Math.min(j - i, 50)).replace("\n","\\n").replace("\r","\\r")); for (int k = i; k < j; k++) owner[k] = lo + i; } i = j; }
        }
        println("STRINGS " + starts.size());
        Map<String,Long> val = new HashMap<>(); int n = 0, nStart = 0; Map<Long,List<String>> refs = new TreeMap<>();
        for (Instruction ins : l.getInstructions(true)) {
            String m = ins.getMnemonicString();
            Object[] d = ins.getNumOperands() > 0 ? ins.getOpObjects(0) : new Object[0];
            String dst = d.length > 0 && !(d[0] instanceof Scalar) ? d[0].toString() : null;
            Long newVal = null;
            try {
                if (m.equals("b.movhi")) { Object[] v = ins.getOpObjects(1); if (v[0] instanceof Scalar) newVal = ((Scalar)v[0]).getUnsignedValue() << 16; }
                else if (m.equals("b.movi")) { Object[] v = ins.getOpObjects(1); if (v[0] instanceof Scalar) newVal = ((Scalar)v[0]).getSignedValue() & 0xffffffffL; }
                else if (m.equals("b.ori") || m.equals("b.addi")) {
                    Object[] s = ins.getOpObjects(1), im = ins.getOpObjects(2);
                    if (s.length > 0 && im.length > 0 && im[0] instanceof Scalar) {
                        String src = s[0].toString(); long imv = m.equals("b.addi") ? ((Scalar)im[0]).getSignedValue() : ((Scalar)im[0]).getUnsignedValue();
                        if (src.equals("r0")) newVal = imv & 0xffffffffL; else if (val.containsKey(src)) newVal = (val.get(src) + imv) & 0xffffffffL;
                        if (newVal != null && newVal >= lo && newVal < hi) {
                            long o = newVal - lo; long own = owner[(int)o];
                            if (own != 0) { Function f = fm.getFunctionContaining(ins.getAddress()); refs.computeIfAbsent(own, k -> new ArrayList<>()).add(ins.getAddress() + (f!=null?"("+f.getName()+")":"") + (own==newVal?"":"+"+(newVal-own))); n++; if (own == newVal) nStart++; }
                        }
                    }
                }
            } catch (Exception e) {}
            if (dst != null) { if (newVal != null) val.put(dst, newVal); else if (!(m.startsWith("b.s") && !m.equals("b.sub")) && !m.startsWith("b.b") && !m.startsWith("b.j") && !m.startsWith("b.sf")) val.remove(dst); }
            if (m.equals("b.jal") || m.equals("b.jalr")) { val.remove("r9"); val.remove("r3"); val.remove("r4"); val.remove("r5"); val.remove("r6"); val.remove("r7"); val.remove("r8"); val.remove("r11"); val.remove("r12"); val.remove("r13"); val.remove("r14"); val.remove("r15"); }
        }
        println("STRREFS " + n + " (" + nStart + " at string start) to " + refs.size() + " distinct strings");
        try (PrintWriter w = new PrintWriter(new FileWriter("build/string_refs.txt"))) {
            for (Map.Entry<Long,List<String>> e : refs.entrySet()) w.println(String.format("0x%x '%s' <- %s", e.getKey(), starts.get(e.getKey()), String.join(" ", e.getValue())));
        }
        String[] want = {"should go to standby","Enter PM/Standby","Change source to","boot key","not hdmi or dvi","Power On","Standby","Active Source","10: Change input","MApp_ZUI_ACT_AppShowInputSource"};
        for (Map.Entry<Long,List<String>> e : refs.entrySet()) for (String wnt : want) if (starts.get(e.getKey()).contains(wnt)) println(String.format("WANT 0x%x '%s' <- %s", e.getKey(), starts.get(e.getKey()), String.join(" ", e.getValue())));
    }
}
