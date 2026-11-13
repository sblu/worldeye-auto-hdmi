import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
public class Lst extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs(); long from = Long.decode(args[0]), to = Long.decode(args[1]);
        Listing l = currentProgram.getListing(); Address a = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(from);
        Instruction ins = l.getInstructionAt(a); if (ins == null) ins = l.getInstructionAfter(a);
        for (; ins != null && ins.getAddress().getOffset() < to; ins = ins.getNext()) {
            StringBuilder b = new StringBuilder(); try { for (byte x : ins.getBytes()) b.append(String.format("%02x", x & 0xff)); } catch (Exception e) {}
            println("LST " + ins.getAddress() + " " + String.format("%-12s", b) + " " + ins);
        }
    }
}
