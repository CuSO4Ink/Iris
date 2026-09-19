using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using HarmonyLib;
using Verse;
using UnityEngine;
namespace IrisSessionRepairs {
 public static class DrawCache {
  sealed class References:IEqualityComparer<Thing>{public bool Equals(Thing a,Thing b)=>ReferenceEquals(a,b);public int GetHashCode(Thing t)=>RuntimeHelpers.GetHashCode(t);}
  public sealed class State {
   public int version=int.MinValue,lastFrame=-1000;public bool dirty=true;
   public readonly HashSet<Thing> members=new HashSet<Thing>(new References());
  }
  static readonly ConditionalWeakTable<List<Thing>,State> states=new ConditionalWeakTable<List<Thing>,State>();
  static readonly AccessTools.FieldRef<List<Thing>,int> versionOf=AccessTools.FieldRefAccess<List<Thing>,int>("_version");
  static readonly AccessTools.FieldRef<DynamicDrawManager,List<Thing>> thingsOf=AccessTools.FieldRefAccess<DynamicDrawManager,List<Thing>>("drawThings");
  static readonly Predicate<Thing> invalid=t=>t==null||!t.Spawned;
  public static void Install(Harmony h){
   try {
    // Patch the existing helpers, preserving their original Harmony state/finalizer pairing.
    h.Patch(AccessTools.Method("IrisFixes.StaleDrawRepair:CleanBeforeDraw"),prefix:new HarmonyMethod(typeof(DrawCache),nameof(Clean)));
    h.Patch(AccessTools.Method("IrisFixes.StaleDrawRepair:RegisterOnce"),prefix:new HarmonyMethod(typeof(DrawCache),nameof(Register)));
    h.Patch(AccessTools.Method(typeof(DynamicDrawManager),"RegisterDrawable"),postfix:new HarmonyMethod(typeof(DrawCache),nameof(Registered)));
    h.Patch(AccessTools.Method(typeof(Thing),"DeSpawn"),prefix:new HarmonyMethod(typeof(DrawCache),nameof(LeavingMap)));
    Log.Message("[Iris Session Repairs] Draw cleanup tracks list changes/despawns; full sweep retained every 120 frames.");
   }catch(Exception e){Log.Error("[Iris Session Repairs] Draw optimization failed: "+e);}
  }
  public static State Get(List<Thing> list)=>states.GetOrCreateValue(list);
  static void Rebuild(List<Thing> list,State s){s.members.Clear();foreach(var t in list)if(t!=null)s.members.Add(t);s.version=versionOf(list);}
  public static bool NeedsSweep(State s,int version,int frame)=>s.dirty||s.version!=version||frame-s.lastFrame>=120||frame<s.lastFrame;
  public static void Sweep(List<Thing> list,State s,int frame){list.RemoveAll(invalid);Rebuild(list,s);s.lastFrame=frame;s.dirty=false;}
  [MethodImpl(MethodImplOptions.NoInlining)] static int Frame()=>Time.frameCount;
  public static bool Clean(List<Thing> __0,bool __1,ref bool __2){
   __2=__1;if(__1)return false;
   var s=Get(__0);int frame=Frame();
   if(NeedsSweep(s,versionOf(__0),frame))Sweep(__0,s,frame);
   return false;
  }
  public static bool Register(Thing __0,List<Thing> __1,ref bool __result){
   if(__0==null){__result=false;return false;}
   var s=Get(__1);if(s.version!=versionOf(__1))Rebuild(__1,s);
   __result=!s.members.Contains(__0);return false;
  }
  public static void Registered(Thing t,List<Thing> ___drawThings){
   var s=Get(___drawThings);int v=versionOf(___drawThings);
   if(v==s.version)return;
   if(v==unchecked(s.version+1)&&___drawThings.Count>0&&ReferenceEquals(___drawThings[___drawThings.Count-1],t)){s.members.Add(t);s.version=v;s.dirty=true;}
   else{s.dirty=true;}
  }
  public static void LeavingMap(Thing __instance){
   var manager=__instance?.Map?.dynamicDrawManager;if(manager==null)return;
   Get(thingsOf(manager)).dirty=true;
  }
 }
}
