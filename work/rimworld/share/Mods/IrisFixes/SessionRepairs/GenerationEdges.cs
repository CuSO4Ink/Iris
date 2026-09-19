using System;
using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using Verse;
using Verse.AI;
using RimWorld;
using RimWorld.QuestGen;
namespace IrisSessionRepairs {
 public static class GenerationEdges {
  public static void Install(Harmony h){
   try {
    h.Patch(AccessTools.Method(typeof(QuestNode_Root_WandererJoin),"GeneratePawn_NewTemp"),prefix:new HarmonyMethod(typeof(GenerationEdges),nameof(LegacyCultivator)));
    foreach(string name in new[]{"IncreasesPopulation","GetQuestLookTargets"})h.Patch(AccessTools.Method(typeof(PawnsArriveQuestPartUtility),name),prefix:new HarmonyMethod(typeof(GenerationEdges),nameof(ValidPawns)));
    foreach(var m in AccessTools.GetDeclaredMethods(typeof(GenConstruct)).Where(m=>m.Name=="CanConstruct"))h.Patch(m,prefix:new HarmonyMethod(typeof(GenerationEdges),nameof(CanConstruct)));
    h.Patch(AccessTools.Method(typeof(Blueprint),"TryReplaceWithSolidThing"),prefix:new HarmonyMethod(typeof(GenerationEdges),nameof(Replace)));
    Log.Message("[Iris Session Repairs] Legacy RI generation bridge and invalid quest/blueprint guards installed.");
   }catch(Exception e){Log.Error("[Iris Session Repairs] Generation edge repair failed: "+e);}
  }
  public static bool LegacyCultivator(QuestNode_Root_WandererJoin __instance,ref Pawn __result){
   if(__instance.GetType().FullName!="WhoXiuXian.QuestNode_RI_Root_WandererJoin_WalkIn")return true;
   __result=__instance.GeneratePawn();return false;
  }
  public static void ValidPawns(ref IEnumerable<Pawn> pawns){pawns=pawns?.Where(p=>p?.def?.race!=null)??Enumerable.Empty<Pawn>();}
  public static bool InvalidBlueprint(Thing t)=>t?.GetType()==typeof(Blueprint_Build)&&t.def?.entityDefToBuild?.frameDef==null;
  public static bool CanConstruct(Thing t,ref bool __result){if(!InvalidBlueprint(t))return true;__result=false;return false;}
  public static bool Replace(Blueprint __instance,Pawn workerPawn,ref Thing createdThing,ref bool jobEnded,ref bool __result){
   if(!InvalidBlueprint(__instance))return true;
   createdThing=null;jobEnded=true;__result=false;
   workerPawn?.jobs?.EndCurrentJob(JobCondition.Incompletable);
   Log.WarningOnce("[Iris Session Repairs] Invalid construction blueprint has no frame: "+__instance.ThingID+". Left in place for manual cancellation; no materials or pawns removed.",__instance.thingIDNumber^719933);
   return false;
  }
 }
}
