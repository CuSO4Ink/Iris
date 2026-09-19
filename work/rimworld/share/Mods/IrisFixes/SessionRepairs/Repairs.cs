using System;
using System.Collections.Generic;
using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using RimWorld;
using Verse;
using Verse.AI;
using UnityEngine;
using System.Runtime.CompilerServices;

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
   HairFit.Install(h);
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
 public static class HairFit {
  static Func<Pawn,bool> usesFace;
  sealed class Seen {public int mask;}
  static readonly ConditionalWeakTable<Pawn,Seen> seen=new ConditionalWeakTable<Pawn,Seen>();
  public static void Install(Harmony h){
   var m=AccessTools.Method("FacialAnimation.FAHelper:ShouldDrawPawn",new[]{typeof(Pawn)});
   if(m==null)return;
   try {
    usesFace=(Func<Pawn,bool>)Delegate.CreateDelegate(typeof(Func<Pawn,bool>),m);
    h.Patch(AccessTools.Method(typeof(PawnRenderNodeWorker),nameof(PawnRenderNodeWorker.ScaleFor)),postfix:new HarmonyMethod(typeof(HairFit),nameof(Scale)){priority=Priority.Last});
    h.Patch(AccessTools.Method(typeof(PawnRenderNodeWorker),nameof(PawnRenderNodeWorker.OffsetFor)),postfix:new HarmonyMethod(typeof(HairFit),nameof(Offset)){priority=Priority.Last});
    Log.Message("[Iris Session Repairs] RK_Mai side-view FA hair fit installed (visual verification pending).");
   } catch(Exception e){Log.Error("[Iris Session Repairs] Hair fit installation failed: "+e);}
  }
  public static bool Matches(string race,string hair,bool side)=>race=="Ratkin"&&hair=="RK_Mai"&&side;
  static bool Applies(PawnRenderNode node,PawnDrawParms parms)=>node is PawnRenderNode_Hair&&Matches(parms.pawn?.def?.defName,parms.pawn?.story?.hairDef?.defName,parms.facing.IsHorizontal)&&usesFace!=null&&usesFace(parms.pawn);
  // Fit the existing Mai artwork to FA's larger side-profile scalp. No asset rewriting.
  // Kept local to this combination; north/south, ears, head and other hairstyles are untouched.
  public static void Scale(PawnRenderNode node,PawnDrawParms parms,ref Vector3 __result){if(Applies(node,parms)){
   __result.x*=1.08f;__result.z*=1.08f;
   // Render workers may run off the main thread: inspect managed properties only, no Mesh/Texture API.
   var record=seen.GetOrCreateValue(parms.pawn);int bit=1<<(parms.facing.AsInt+(parms.Portrait?4:0));
   bool report=false;lock(record){if((record.mask&bit)==0){record.mask|=bit;report=true;}}
   if(report)Log.Message("[Iris Hair Fit] pawn="+parms.pawn.ThingID+" facing="+parms.facing.AsInt+" portrait="+parms.Portrait+" flip="+parms.flipHead+" localScale="+__result+" nodeSize="+node.Props.drawSize+" parentSize="+node.parent?.Props.drawSize+". Side-view contour fit still requires visual verification.");
  }}
  public static void Offset(PawnRenderNode node,PawnDrawParms parms,ref Vector3 __result){if(Applies(node,parms))__result.z+=0.015f;}
 }
}
