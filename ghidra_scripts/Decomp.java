import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.*;
public class Decomp extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs(); String out = args[0];
        DecompInterface di = new DecompInterface(); di.openProgram(currentProgram);
        FunctionManager fm = currentProgram.getFunctionManager();
        try (PrintWriter w = new PrintWriter(new FileWriter(out))) {
            for (int i = 1; i < args.length; i++) {
                Function f = fm.getFunctionAt(currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(Long.decode(args[i])));
                if (f == null) { w.println("// no function at " + args[i]); continue; }
                DecompileResults r = di.decompileFunction(f, 120, monitor);
                StringBuilder cs = new StringBuilder(); for (Function c : f.getCallingFunctions(monitor)) cs.append(c.getName()).append(" ");
                w.println("// ==== " + f.getName() + " size=" + f.getBody().getNumAddresses() + " callers: " + cs);
                w.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// failed: " + r.getErrorMessage());
            }
        }
        println("WROTE " + out);
    }
}
