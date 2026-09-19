using System;
using System.Linq.Expressions;
using HarmonyLib;
using Verse;

namespace IrisSessionRepairs {
 public static class NativeHeadCompatibility {
  static Type controllerType;
  static Func<ThingComp,Def> faceDef;
  public static bool Target(string race,string nativeHead)=>race=="Ratkin" || nativeHead?.StartsWith("SmeltedLoongHead",StringComparison.Ordinal)==true;
  public static bool Matches(string race,string nativeHead,string faHead)=>Target(race,nativeHead) &&
   (faHead==null || faHead=="HeadNormal" || faHead=="HeadPointy" || faHead=="HeadSquare");
  public static void Install(Harmony h){
   controllerType=AccessTools.TypeByName("FacialAnimation.HeadControllerComp");if(controllerType==null)return;
   try {
    var field=AccessTools.Field(controllerType,"faceType");
    if(field==null||!typeof(Def).IsAssignableFrom(field.FieldType))throw new InvalidOperationException("FA head-controller field changed.");
    var comp=Expression.Parameter(typeof(ThingComp),"comp");
    faceDef=Expression.Lambda<Func<ThingComp,Def>>(Expression.Convert(Expression.Field(Expression.Convert(comp,controllerType),field),typeof(Def)),comp).Compile();
    // Both decisions must agree: prevent custom face nodes AND keep the native head/hair path.
    h.Patch(AccessTools.Method("FacialAnimation.DrawFaceGraphicsComp:CheckEnableDrawing",new[]{typeof(Pawn)}),postfix:new HarmonyMethod(typeof(NativeHeadCompatibility),nameof(KeepNative)));
    h.Patch(AccessTools.Method("FacialAnimation.FAHelper:ShouldDrawPawn",new[]{typeof(Pawn)}),postfix:new HarmonyMethod(typeof(NativeHeadCompatibility),nameof(KeepNative)));
    Log.Message("[Iris Session Repairs] Ratkin / Smelted Loong native heads retained instead of generic FA faces. Dedicated FA heads and other races unchanged; removed empirical hair scaling.");
   }catch(Exception e){Log.Error("[Iris Session Repairs] Native head compatibility failed: "+e);}
  }
  public static bool UseNative(Pawn pawn){
   if(pawn==null||!Target(pawn.def?.defName,pawn.story?.headType?.defName))return false;
   var comps=pawn.AllComps;
   if(comps!=null)foreach(var comp in comps)if(controllerType?.IsInstanceOfType(comp)==true)
    return Matches(pawn.def.defName,pawn.story?.headType?.defName,faceDef(comp)?.defName);
   return true;
  }
  public static void KeepNative(Pawn pawn,ref bool __result){if(__result&&UseNative(pawn))__result=false;}
 }
}
