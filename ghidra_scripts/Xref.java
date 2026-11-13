import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
public class Xref extends GhidraScript {
    public void run() throws Exception {
        for (String a : getScriptArgs()) {
            long v = Long.decode(a);
            for (Reference r : getReferencesTo(toAddr(v))) {
                Function c = currentProgram.getFunctionManager().getFunctionContaining(r.getFromAddress());
                println(String.format("XREF 0x%x <- %s %s %s", v, r.getFromAddress(), r.getReferenceType(), c != null ? c.getName() : "-"));
            }
        }
    }
}
