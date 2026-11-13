import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.address.*;
public class CallArgs extends GhidraScript {
    public void run() throws Exception {
        for (String a : getScriptArgs()) {
            Address t = toAddr(Long.decode(a));
            for (Reference r : getReferencesTo(t)) {
                if (!r.getReferenceType().isCall()) continue;
                Instruction ins = getInstructionAt(r.getFromAddress()); String arg = "?";
                Instruction p = ins;
                for (int i = 0; i < 6 && p != null; i++) { p = p.getPrevious(); if (p == null) break; String s = p.toString(); if (s.contains(" r3,")) { arg = s; break; } }
                Function c = getFunctionContaining(r.getFromAddress());
                println(String.format("CALL %s <- %s %s | %s", a, r.getFromAddress(), c != null ? c.getName() : "-", arg));
            }
        }
    }
}
