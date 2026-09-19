using System;
using System.Collections.Generic;
using System.Reflection.Emit;
using HarmonyLib;
using Verse;
namespace IrisSessionRepairs {
 public static class SpawnerContext {
  public sealed class Frame {public Thing thing;public Map map;public Frame previous;}
  [ThreadStatic] static Frame current;
  static Type compType;
  public static void Install(Harmony h){
   compType=AccessTools.TypeByName("VFEInsectoids.CompInsectSpawner");if(compType==null)return;
   try {
    h.Patch(AccessTools.Method(typeof(Thing),nameof(Thing.TakeDamage)),prefix:new HarmonyMethod(typeof(SpawnerContext),nameof(Begin)),finalizer:new HarmonyMethod(typeof(SpawnerContext),nameof(End)));
    h.Patch(AccessTools.Method(compType,"PostPostApplyDamage"),prefix:new HarmonyMethod(typeof(SpawnerContext),nameof(HasMap)),transpiler:new HarmonyMethod(typeof(SpawnerContext),nameof(UseDamageMap)));
    Log.Message("[Iris Session Repairs] Insect-spawner damage map preserved, including nested/fatal damage.");
   }catch(Exception e){Log.Error("[Iris Session Repairs] Spawner context failed: "+e);}
  }
  public static void Begin(Thing __instance,out Frame __state){
   __state=null;
   if(!(__instance is Building b)||b.Map==null||b.AllComps==null)return;
   foreach(var comp in b.AllComps)if(compType.IsInstanceOfType(comp)){
    __state=Push(b,b.Map);break;
   }
  }
  public static Frame Push(Thing thing,Map map){return current=new Frame{thing=thing,map=map,previous=current};}
  public static void End(Frame __state){if(__state!=null)current=__state.previous;}
  public static Map MapFor(Thing thing){
   if(thing?.Map!=null)return thing.Map;
   for(var f=current;f!=null;f=f.previous)if(ReferenceEquals(f.thing,thing))return f.map;
   return null;
  }
  public static bool HasMap(ThingComp __instance)=>MapFor(__instance?.parent)!=null;
  public static IEnumerable<CodeInstruction> UseDamageMap(IEnumerable<CodeInstruction> source){
   int count=0;var getter=AccessTools.PropertyGetter(typeof(Thing),nameof(Thing.Map));
   foreach(var c in source){if(c.Calls(getter)){c.opcode=OpCodes.Call;c.operand=AccessTools.Method(typeof(SpawnerContext),nameof(MapFor));count++;}yield return c;}
   if(count!=1)throw new InvalidOperationException("Insect spawner map lookup changed.");
  }
 }
}
