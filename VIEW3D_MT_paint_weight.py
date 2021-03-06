# 「3Dビュー」エリア > 「ウェイトペイント」モード > 「ウェイト」メニュー
# "3D View" Area > "Weight Paint" Mode > "Weights" Menu

import bpy, bmesh
from bpy.props import *

################
# オペレーター #
################

class MargeSelectedVertexGroup(bpy.types.Operator):
	bl_idname = "paint.marge_selected_vertex_group"
	bl_label = "Combine Weights"
	bl_description = "Weight of selected bone and same vertex group merges"
	bl_options = {'REGISTER', 'UNDO'}

	isNewVertGroup : BoolProperty(name="Create new vertex group", default=False)
	ext : StringProperty(name="End of new vertex group name", default="... Such as combine")
	items = [
		('1', "Merge selected bones' weight", "", 1),
		('2', "Select another bone and merge their weight", "", 2),
		]
	method : EnumProperty(items=items, name="Select manually or not")
	vgroup_name : StringProperty(name="Vertex group to merge", default="")

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	def draw(self, context):
		self.layout.prop(self, "method", text="Method")
		if self.method == '2':
			self.layout.prop_search(self, "vgroup_name", context.active_object, "vertex_groups", text="Select group to merge", translate=True, icon='GROUP_VERTEX')
		row = self.layout.row()
		row.prop(self, "isNewVertGroup")
		row.prop(self, "ext")
	def execute(self, context):
		obj = context.active_object
		me = obj.data
		if (self.isNewVertGroup):
			newVg = obj.vertex_groups.new(name=context.active_pose_bone.name+self.ext)
		else:
			newVg = obj.vertex_groups[context.active_pose_bone.name]
		boneNames = []
		if (self.method == '2' and not self.vgroup_name) or (self.method == '1' and len(context.selected_pose_bones) <= 1):
			self.report(type={"ERROR"}, message="Please select two or more bones")
			return {"CANCELLED"}
		for bone in context.selected_pose_bones:
			boneNames.append(bone.name)
		if self.vgroup_name and not self.vgroup_name in boneNames:
			boneNames.append(self.vgroup_name)
		for vert in me.vertices:
			for vg in vert.groups:
				if (self.isNewVertGroup or newVg.name != obj.vertex_groups[vg.group].name):
					if (obj.vertex_groups[vg.group].name in boneNames):
						newVg.add([vert.index], vg.weight, 'ADD')
		bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
		obj.vertex_groups.active_index = newVg.index
		return {'FINISHED'}

class RemoveSelectedVertexGroup(bpy.types.Operator):
	bl_idname = "paint.remove_selected_vertex_group"
	bl_label = "Subtraction Weights"
	bl_description = "Subtracts weight of selected bone and same vertex groups"
	bl_options = {'REGISTER', 'UNDO'}

	items = [
		('1', "Subtract selected bones' weight from active one's", "", 1),
		('2', "Select another bone and subtract its weight", "", 2),
		]
	method : EnumProperty(items=items, name="Select manually or not")
	vgroup_name : StringProperty(name="Vertex group to merge", default="")

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	def draw(self, context):
		self.layout.prop(self, "method", text="Method")
		if self.method == '2':
			self.layout.prop_search(self, "vgroup_name", context.active_object, "vertex_groups", text="Select group to merge", translate=True, icon='GROUP_VERTEX')
	def execute(self, context):
		obj = context.active_object
		me = obj.data
		newVg = obj.vertex_groups[context.active_pose_bone.name]
		boneNames = []
		if (self.method == '2' and not self.vgroup_name) or (self.method == '1' and len(context.selected_pose_bones) <= 1):
			self.report(type={"ERROR"}, message="Please select two or more bones")
			return {"CANCELLED"}
		for bone in context.selected_pose_bones:
			boneNames.append(bone.name)
		if self.vgroup_name and not self.vgroup_name in boneNames:
			boneNames.append(self.vgroup_name)
		for vert in me.vertices:
			for vg in vert.groups:
				if (newVg.name != obj.vertex_groups[vg.group].name):
					if (obj.vertex_groups[vg.group].name in boneNames):
						newVg.add([vert.index], vg.weight, 'SUBTRACT')
		bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
		return {'FINISHED'}

class VertexGroupAverageAll(bpy.types.Operator):
	bl_idname = "mesh.vertex_group_average_all"
	bl_label = "Fill average weight of all vertices"
	bl_description = "In average weight of all, fills all vertices"
	bl_options = {'REGISTER', 'UNDO'}

	strength : FloatProperty(name="Strength", default=1, min=0, max=1, soft_min=0, soft_max=1, step=10, precision=3)

	def execute(self, context):
		for obj in context.selected_objects:
			if (obj.type == "MESH"):
				vgs = []
				for i in range(len(obj.vertex_groups)):
					vgs.append([])
				vertCount = 0
				for vert in obj.data.vertices:
					for vg in vert.groups:
						vgs[vg.group].append(vg.weight)
					vertCount += 1
				vg_average = []
				for vg in vgs:
					vg_average.append(0)
					for w in vg:
						vg_average[-1] += w
					vg_average[-1] /= vertCount
				i = 0
				for vg in obj.vertex_groups:
					for vert in obj.data.vertices:
						for g in vert.groups:
							if (obj.vertex_groups[g.group] == vg):
								w = g.weight
								break
						else:
							w = 0
						w = (vg_average[i] * self.strength) + (w * (1-self.strength))
						vg.add([vert.index], w, "REPLACE")
					i += 1
		bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
		return {'FINISHED'}

class ApplyDynamicPaint(bpy.types.Operator):
	bl_idname = "mesh.apply_dynamic_paint"
	bl_label = "Paint objects overlap"
	bl_description = "I painted weight of portion that overlaps other selected objects"
	bl_options = {'REGISTER', 'UNDO'}

	isNew : BoolProperty(name="To new vertex group", default=False)
	distance : FloatProperty(name="Distance", default=1.0, min=0, max=100, soft_min=0, soft_max=100, step=10, precision=3)
	items = [
		("ADD", "Add", "", 1),
		("SUBTRACT", "Sub", "", 2),
		("REPLACE", "Replace", "", 3),
		]
	mode : EnumProperty(items=items, name="Fill Method")

	def execute(self, context):
		activeObj = context.active_object
		preActiveVg = activeObj.vertex_groups.active
		isNew = self.isNew
		if (not preActiveVg):
			isNew = True
		brushObjs = []

		for obj in context.selected_objects:
			if (activeObj.name != obj.name):
				brushObjs.append(obj)

		bpy.ops.object.mode_set(mode="OBJECT")

		for obj in brushObjs:
			bpy.context.view_layer.objects.active = obj
			bpy.ops.object.modifier_add(type='DYNAMIC_PAINT')
			obj.modifiers[-1].ui_type = 'BRUSH'
			bpy.ops.dpaint.type_toggle(type='BRUSH')
			obj.modifiers[-1].brush_settings.paint_source = 'VOLUME_DISTANCE'
			obj.modifiers[-1].brush_settings.paint_distance = self.distance

		bpy.context.view_layer.objects.active = activeObj
		bpy.ops.object.modifier_add(type='DYNAMIC_PAINT')
		bpy.ops.dpaint.type_toggle(type='CANVAS')
		activeObj.modifiers[-1].canvas_settings.canvas_surfaces[-1].surface_type = 'WEIGHT'
		bpy.ops.dpaint.output_toggle(output='A')
		dpVg = activeObj.vertex_groups[-1]
		# mod_soft_body = activeObj.modifiers.new(name="Soft Body", type='SOFT_BODY')

		#"Dynamic Paint weight group isn't updated unless weight has been assigned" というバグが2.80にある(あった?)
		#おそらくこれに関連し、スクリプト経由でダイナミックペイントを適用する際に
		#何もしない場合、作成される頂点グループ dp_weight の中身がリセットされる
		#これに対応するため、ここではソフトボディに関連付けして中身を固定している

		bpy.ops.object.modifier_add(type='SOFT_BODY')
		activeObj.modifiers[-2].settings.vertex_group_mass = dpVg.name
		bpy.ops.object.modifier_apply(modifier=activeObj.modifiers[-1].name)
		activeObj.modifiers.remove(activeObj.modifiers[-1])#ソフトボディ除去削除

		if (not isNew):
			me = activeObj.data
			for vert in me.vertices:
				for vg in vert.groups:
					if (activeObj.vertex_groups[vg.group].name == dpVg.name):
						preActiveVg.add([vert.index], vg.weight, self.mode)
						break
			activeObj.vertex_groups.remove(dpVg)
			activeObj.vertex_groups.active_index = preActiveVg.index
		bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
		for obj in brushObjs:
			obj.modifiers.remove(obj.modifiers[-1])
		return {'FINISHED'}


class BlurWeight(bpy.types.Operator):
	bl_idname = "mesh.blur_weight"
	bl_label = "Vertex Group Blur"
	bl_description = "Blurs active or all vertex groups"
	bl_options = {'REGISTER', 'UNDO'}

	items = [
		('ACTIVE', "Active Only", "", 1),
		('ALL', "All", "", 2),
		]
	mode : EnumProperty(items=items, name="Target", default='ACTIVE')
	blur_count : IntProperty(name="Repeat Count", default=10, min=1, max=100, soft_min=1, soft_max=100, step=1)
	use_clean : BoolProperty(name="Remove weight of 0.0", default=True)


	def execute(self, context):
		activeObj = context.active_object
		if (not activeObj):
			self.report(type={'ERROR'}, message="There is no active object")
			return {'CANCELLED'}
		if (activeObj.type != 'MESH'):
			self.report(type={'ERROR'}, message="Try run on mesh object")
			return {'CANCELLED'}
		pre_mode = activeObj.mode
		bpy.ops.object.mode_set(mode='OBJECT')
		me = activeObj.data
		target_weights = []
		if (self.mode == 'ACTIVE'):
			target_weights.append(activeObj.vertex_groups.active)
		elif (self.mode == 'ALL'):
			for vg in activeObj.vertex_groups:
				target_weights.append(vg)
		bm = bmesh.new()
		bm.from_mesh(me)
		for count in range(self.blur_count):
			for vg in target_weights:
				vg_index = vg.index
				new_weights = []
				for vert in bm.verts:
					for group in me.vertices[vert.index].groups:
						if (group.group == vg_index):
							my_weight = group.weight
							break
					else:
						my_weight = 0.0
					near_weights = []
					for edge in vert.link_edges:
						for v in edge.verts:
							if (v.index != vert.index):
								edges_vert = v
								break
						for group in me.vertices[edges_vert.index].groups:
							if (group.group == vg_index):
								near_weights.append(group.weight)
								break
						else:
							near_weights.append(0.0)
					near_weight_average = 0
					for weight in near_weights:
						near_weight_average += weight
					try:
						near_weight_average /= len(near_weights)
					except ZeroDivisionError:
						near_weight_average = 0.0
					new_weights.append( (my_weight*2 + near_weight_average) / 3 )
				for vert, weight in zip(me.vertices, new_weights):
					if (self.use_clean and weight <= 0.000001):
						vg.remove([vert.index])
					else:
						vg.add([vert.index], weight, 'REPLACE')
		bm.free()
		bpy.ops.object.mode_set(mode=pre_mode)
		return {'FINISHED'}

################
# クラスの登録 #
################

classes = [
	MargeSelectedVertexGroup,
	RemoveSelectedVertexGroup,
	VertexGroupAverageAll,
	ApplyDynamicPaint,
	BlurWeight
]

def register():
	for cls in classes:
		bpy.utils.register_class(cls)

def unregister():
	for cls in classes:
		bpy.utils.unregister_class(cls)


################
# メニュー追加 #
################

# メニューのオン/オフの判定
def IsMenuEnable(self_id):
	for id in bpy.context.preferences.addons[__name__.partition('.')[0]].preferences.disabled_menu.split(','):
		if (id == self_id):
			return False
	else:
		return True

# メニューを登録する関数
def menu(self, context):
	if (IsMenuEnable(__name__.split('.')[-1])):
		self.layout.separator()
		self.layout.operator(MargeSelectedVertexGroup.bl_idname, icon="PLUGIN")
		self.layout.operator(RemoveSelectedVertexGroup.bl_idname, icon="PLUGIN")
		self.layout.separator()
		self.layout.operator(BlurWeight.bl_idname, text="Blur Active", icon="PLUGIN").mode = 'ACTIVE'
		self.layout.operator(BlurWeight.bl_idname, text="Blur All", icon="PLUGIN").mode = 'ALL'
		self.layout.separator()
		self.layout.operator(VertexGroupAverageAll.bl_idname, icon="PLUGIN")
		self.layout.separator()
		self.layout.operator(ApplyDynamicPaint.bl_idname, icon="PLUGIN")
	if (context.preferences.addons[__name__.partition('.')[0]].preferences.use_disabled_menu):
		self.layout.separator()
		self.layout.operator('wm.toggle_menu_enable', icon='CANCEL').id = __name__.split('.')[-1]
