using System;
using System.Collections.Generic;
using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using RimWorld;
using Verse;
using Verse.AI;

namespace IrisSessionRepairs {
 [StaticConstructorOnStartup]
 public static class Startup {
  static Startup() {
   var h=new Harmony("local.iris.sessionrepairs");
   Install(h,AccessTools.Method(typeof(WanderUtility),nameof(WanderUtility.BestCloseWanderRoot)),nameof(Repairs.WanderRoot));
   Install(h,AccessTools.Method(typeof(JobGiver_Wander),"TryGiveJob"),nameof(Repairs.WanderJob));
   SpawnerContext.Install(h);
   DrawCache.Install(h);
   GenerationEdges.Install(h);
   NativeHeadCompatibility.Install(h);
   var wait=AccessTools.Method(typeof(JobDriver_Wait),"CheckForAutoAttack");
   try {
    h.Patch(wait,prefix:new HarmonyMethod(typeof(Repairs),nameof(Repairs.WaitContext)),
      transpiler:new HarmonyMethod(typeof(Repairs),nameof(Repairs.WaitCalls)){priority=Priority.Last},
      finalizer:new HarmonyMethod(typeof(Repairs),nameof(Repairs.WaitDiagnostic)));
    Log.Message("[Iris Session Repairs] Wait lifecycle guards installed.");
   } catch(Exception e){Log.Error("[Iris Session Repairs] Wait patch failed: "+e);}
  }
  static void Install(Harmony h,MethodBase target,string method) {
   if(target==null)return;
   try {h.Patch(target,prefix:new HarmonyMethod(typeof(Repairs),method));Log.Message("[Iris Session Repairs] Installed "+method);}
   catch(Exception e){Log.Error("[Iris Session Repairs] "+method+" failed: "+e);}
  }
 }
 public static class Repairs {
  public static bool OnMap(Pawn p)=>p!=null&&!p.Destroyed&&p.Spawned&&p.Map!=null;
  public static bool WanderRoot(Pawn pawn,ref IntVec3 __result) {
   if(OnMap(pawn))return true;
   __result=IntVec3.Invalid;return false;
  }
  public static bool WanderJob(Pawn pawn,ref Job __result) {
   if(OnMap(pawn))return true;
   __result=null;return false;
  }
  public static bool WaitContext(JobDriver_Wait __instance)=>OnMap(__instance?.pawn)&&__instance.job!=null;
  public static bool InBounds(IntVec3 cell,Map map)=>map!=null&&cell.InBounds(map);
  public static bool BeatFire(Pawn_NativeVerbs verbs,Fire fire)=>verbs!=null&&fire!=null&&fire.Spawned&&verbs.TryBeatFire(fire);
  public static IEnumerable<CodeInstruction> WaitCalls(IEnumerable<CodeInstruction> source) {
   int bounds=0,fire=0;
   var oldBounds=AccessTools.Method(typeof(GenGrid),nameof(GenGrid.InBounds),new[]{typeof(IntVec3),typeof(Map)});
   var oldFire=AccessTools.Method(typeof(Pawn_NativeVerbs),nameof(Pawn_NativeVerbs.TryBeatFire));
   foreach(var c in source){
    if(c.Calls(oldBounds)){c.opcode=OpCodes.Call;c.operand=AccessTools.Method(typeof(Repairs),nameof(InBounds));bounds++;}
    if(c.Calls(oldFire)){c.opcode=OpCodes.Call;c.operand=AccessTools.Method(typeof(Repairs),nameof(BeatFire));fire++;}
    yield return c;
   }
   if(bounds!=1||fire!=1)throw new InvalidOperationException("Wait implementation changed; expected one bounds check and one beat-fire call.");
  }
  static bool diagnosticWritten;
  // Preserve the exception, while recording lifecycle state missing from the original trace.
  public static void WaitDiagnostic(JobDriver_Wait __instance,Exception __exception){
   if(__exception==null||diagnosticWritten)return;diagnosticWritten=true;
   var p=__instance?.pawn;
   Log.Warning("[Iris Session Repairs] Auto-attack failure context: pawn="+p?.ThingID+", spawned="+p?.Spawned+", destroyed="+p?.Destroyed+", map="+p?.Map?.uniqueID+", natives="+(p?.natives!=null)+", stances="+(p?.stances!=null)+", melee="+(p?.meleeVerbs!=null)+", job="+__instance?.job?.def?.defName);
  }
 }
}
