import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
public class FnAt extends GhidraScript {
    public void run() throws Exception {
        for (String a : getScriptArgs()) {
            long v = Long.decode(a);
            Function f = currentProgram.getFunctionManager().getFunctionAt(toAddr(v));
            Function c = currentProgram.getFunctionManager().getFunctionContaining(toAddr(v));
            println(String.format("AT 0x%x start=%s containing=%s", v, f != null ? f.getName() : "-", c != null ? c.getName() : "-"));
        }
    }
}
