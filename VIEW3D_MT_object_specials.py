# 「3Dビュー」エリア > 「オブジェクト」モード > 「W」キー
# "3D View" Area > "Object" Mode > "W" Key

import bpy, bmesh, mathutils
import re, random
from bpy.props import *

################
# オペレーター #
################

class VertexGroupTransferWeightObjmode(bpy.types.Operator):
	bl_idname = "object.vertex_group_transfer_weight_objmode"
	bl_label = "Weight Transfer"
	bl_description = "From mesh during selection of other active forwarding weight paint"
	bl_options = {'REGISTER', 'UNDO'}

	toActive : BoolProperty(name="Selected to active", default=True)
	isDeleteWeights : BoolProperty(name="Before delete all weights", default=True)
	items = [
		('TOPOLOGY', "Topology", "", 1),
		('NEAREST', "Nearest Vertex", "", 2),
		('POLY_NEAREST', "Nearest Face Vertex", "", 3),
		('POLYINTERP_VNORPROJ', "Projected Face Interpolated", "", 4),
		]
	method : EnumProperty(items=items, name="Method", default="NEAREST")

	def execute(self, context):
		if (self.isDeleteWeights):
			try:
				bpy.ops.object.vertex_group_remove(all=True)
			except RuntimeError:
				pass
		bpy.ops.object.data_transfer(use_reverse_transfer=self.toActive, data_type='VGROUP_WEIGHTS', vert_mapping=self.method, layers_select_src='ALL', layers_select_dst='NAME', mix_mode='REPLACE')
		#bpy.ops.object.vertex_group_transfer_weight(group_select_mode='WT_REPLACE_ALL_VERTEX_GROUPS', method=self.method, replace_mode='WT_REPLACE_ALL_WEIGHTS')
		return {'FINISHED'}

class ToggleSmooth(bpy.types.Operator):
	bl_idname = "object.toggle_smooth"
	bl_label = "Toggle Smooth/Flat"
	bl_description = "Toggles selected mesh object smooth / flat state"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			if (obj.type == 'MESH'):
				return True
		return False
	def execute(self, context):
		activeObj = context.active_object
		if (activeObj.type == 'MESH'):
			me = activeObj.data
			is_smoothed = False
			if (1 <= len(me.polygons)):
				if (me.polygons[0].use_smooth):
					is_smoothed = True
			for obj in context.selected_objects:
				if (is_smoothed):
					bpy.ops.object.shade_flat()
				else:
					bpy.ops.object.shade_smooth()
		else:
			self.report(type={'ERROR'}, message="Try mesh object to activate it")
			return {'CANCELLED'}
		if (is_smoothed):
			self.report(type={'WARNING'}, message="Have flat mesh object")
		else:
			self.report(type={'INFO'}, message="Mesh objects smoothly")
		return {'FINISHED'}

class VertexGroupTransfer(bpy.types.Operator):
	bl_idname = "object.vertex_group_transfer"
	bl_label = "Transfer Vertex Group"
	bl_description = "Transfers to other selected mesh vertex group active mesh"
	bl_options = {'REGISTER', 'UNDO'}

	vertex_group_remove_all : BoolProperty(name="Delete all vertex groups first", default=False)
	vertex_group_clean : BoolProperty(name="Clean Vertex Groups", default=True)
	vertex_group_delete : BoolProperty(name="Delete no-assignment vertex group", default=True)

	@classmethod
	def poll(cls, context):
		if (len(context.selected_objects) <= 1):
			return False
		source_objs = []
		for obj in context.selected_objects:
			if (obj.type == 'MESH' and context.object.name != obj.name):
				source_objs.append(obj)
		if (len(source_objs) <= 0):
			return False
		for obj in source_objs:
			if (1 <= len(obj.vertex_groups)):
				return True
		return False
	def execute(self, context):
		if (context.active_object.type != 'MESH'):
			self.report(type={'ERROR'}, message="Please run mesh object is active")
			return {'CANCELLED'}
		source_objs = []
		for obj in context.selected_objects:
			if (obj.type == 'MESH' and context.active_object.name != obj.name):
				source_objs.append(obj)
		if (len(source_objs) <= 0):
			self.report(type={'ERROR'}, message="Please run selected mesh object to two or more")
			return {'CANCELLED'}
		if (0 < len(context.active_object.vertex_groups) and self.vertex_group_remove_all):
			bpy.ops.object.vertex_group_remove(all=True)
		me = context.active_object.data
		vert_mapping = 'NEAREST'
		for obj in source_objs:
			if (len(obj.data.polygons) <= 0):
				for obj2 in source_objs:
					if (len(obj.data.edges) <= 0):
						break
				else:
					vert_mapping = 'EDGEINTERP_NEAREST'
				break
		else:
			vert_mapping = 'POLYINTERP_NEAREST'
		#use_reverse_transfer=True の場合、layers_select_dst と
		#layers_select_src の値を逆にする必要があるという謎のバグ?あり
		try:
			bpy.ops.object.data_transfer(use_reverse_transfer=True, data_type='VGROUP_WEIGHTS', use_create=True, vert_mapping=vert_mapping,  layers_select_dst='ALL', layers_select_src='NAME')
		except TypeError:
			ops.object.data_transfer(use_reverse_transfer=True, data_type='VGROUP_WEIGHTS', use_create=True, vert_mapping=vert_mapping,  layers_select_src='ALL', layers_select_dst='NAME')
		if (self.vertex_group_clean):
			bpy.ops.object.vertex_group_clean(group_select_mode='ALL', limit=0, keep_single=False)
		if (self.vertex_group_delete):
			bpy.ops.mesh.remove_empty_vertex_groups()
		return {'FINISHED'}

class VertexGroupAverageAll(bpy.types.Operator):
	bl_idname = "mesh.vertex_group_average_all_2"
	bl_label = "Fill average weight of all vertices"
	bl_description = "In average weight of all, fills all vertices"
	bl_options = {'REGISTER', 'UNDO'}

	strength : FloatProperty(name="Strength", default=1, min=0, max=1, soft_min=0, soft_max=1, step=10, precision=3)

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			if (obj.type == 'MESH'):
				if (1 <= len(obj.vertex_groups)):
					return True
		return False
	def execute(self, context):
		pre_mode = context.mode
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
		bpy.ops.object.mode_set(mode="OBJECT")
		bpy.ops.object.mode_set(mode=pre_mode)
		return {'FINISHED'}

##########################
# オペレーター(特殊処理) #
_STORE_ITEMS = []#保存用グローバル変数：EnumPropertyの動的なitems作成におけるバグへの対処用
##########################

class CreateVertexToMetaball(bpy.types.Operator):
	bl_idname = "object.create_vertex_to_metaball"
	bl_label = "Hook Metaballs"
	bl_description = "Have made new metaballs to vertices of selected mesh object"
	bl_options = {'REGISTER', 'UNDO'}

	name : StringProperty(name="Metaball Name", default="Mball")
	size : FloatProperty(name="Size", default=0.1, min=0.001, max=10, soft_min=0.001, soft_max=10, step=1, precision=3)
	resolution : FloatProperty(name="Resolution", default=0.1, min=0.001, max=10, soft_min=0.001, soft_max=10, step=0.5, precision=3)
	isUseVg : BoolProperty(name="Size from vertex group", default=False)

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			if (obj.type == 'MESH'):
				return True
		return False
	def execute(self, context):
		for obj in context.selected_objects:
			if (obj.type == 'MESH'):
				me = obj.data
				metas = []
				active_vg_index = obj.vertex_groups.active_index
				for i in range(len(me.vertices)):
					multi = 1.0
					if (self.isUseVg):
						for element in me.vertices[i].groups:
							if (element.group == active_vg_index):
								multi = element.weight
								break
					meta = bpy.data.metaballs.new(self.name)
					metas.append( bpy.data.objects.new(self.name, meta) )
					meta.elements.new()
					meta.update_method = 'NEVER'
					meta.resolution = self.resolution
					metas[-1].name = self.name
					size = self.size * multi
					metas[-1].scale = (size, size, size)
					metas[-1].parent = obj
					metas[-1].parent_type = 'VERTEX'
					metas[-1].parent_vertices = (i, 0, 0)
				bpy.ops.object.select_all(action='DESELECT')
				for meta in metas:
					context.view_layer.active_layer_collection.collection.objects.link(meta)
					meta.select_set(True)
				bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
				metas[-1].parent_type = metas[-1].parent_type
				base_obj = metas[0] #context.scene.objects[re.sub(r'\.\d+$', '', metas[0].name)]
				bpy.context.view_layer.objects.active = base_obj
				base_obj.data.update_method = 'UPDATE_ALWAYS'
				#context.scene.update()
		return {'FINISHED'}

class AddGreasePencilPathMetaballs(bpy.types.Operator):
	bl_idname = "object.add_grease_pencil_path_metaballs"
	bl_label = "Metaballs to GreasePencil"
	bl_description = "metaballs align with active grease pencil"
	bl_properties = "act_layer"
	bl_options = {'REGISTER', 'UNDO'}

	dissolve_verts_count : IntProperty(name="Density", default=3, min=1, max=100, soft_min=1, soft_max=100, step=1)
	radius : FloatProperty(name="Metaball Size", default=0.05, min=0, max=1, soft_min=0, soft_max=1, step=0.2, precision=3)
	resolution : FloatProperty(name="Metaball Resolution", default=0.05, min=0.001, max=1, soft_min=0.001, soft_max=1, step=0.2, precision=3)
	gp_name : StringProperty(name="Target GreasePencil / Annotation", default="")

	def item_callback(self, context):
		_STORE_ITEMS.clear()
		names = [n for n in bpy.data.grease_pencils[self.gp_name].layers.keys()]
		for idx, name in enumerate(names):
			_STORE_ITEMS.append((str(idx), name, "", idx))
		print(_STORE_ITEMS[0])#作成したリストの要素がうまく認識されないバグ?への一応の対処
		return _STORE_ITEMS
	act_layer : EnumProperty(name="Layers", items=item_callback)

	def __init__(self):
		if bpy.context.active_object and bpy.context.active_object.type == 'GPENCIL':
			self.gp_name = bpy.context.active_object.data.name
		else:
			for gp in bpy.data.grease_pencils:
				if gp.is_annotation == True:
					self.gp_name = gp.name
					break
			else:
				self.gp_name = bpy.data.grease_pencils[0].name
	def invoke(self, context, event):
		if context.active_object and context.active_object.type == 'GPENCIL':
			self.gp_name = context.active_object.data.name
			self.execute(context)
			return {'FINISHED'}
		else:
			return context.window_manager.invoke_props_dialog(self)
	def draw(self, context):
		self.layout.prop_search(self, "gp_name", bpy.data, "grease_pencils",text="Target", translate=True, icon='GP_SELECT_STROKES')
		row = self.layout.row()
		row.label(text="Target Layer ")
		row.props_enum(self, "act_layer")

	def execute(self, context):
		gpen = bpy.data.grease_pencils[self.gp_name]
		if not gpen.is_annotation:
			try:
				obj = bpy.data.objects[self.gp_name]
			except KeyError:
				self.report(type={'ERROR'}, message="Please make object's name equal to greasepencil's name")
				return {'CANCELLED'}
		else:
			obj = bpy.data.objects.new(name=self.gp_name, object_data=gpen)
			context.view_layer.active_layer_collection.collection.objects.link(obj)
		context.view_layer.objects.active = obj
		bpy.ops.gpencil.layer_active(layer=int(self.act_layer))
		pre_selectable_objects = context.selectable_objects
		try:
			bpy.ops.gpencil.convert(type='CURVE', use_normalize_weights=False, use_link_strokes=False, use_timing_data=True)
		except RuntimeError:
				self.report(type={'ERROR'}, message="Converting GreasePencil failed. (Maybe, active Layer doesn\'t contain 'Line' data)")
				return {'CANCELLED'}	
		for obj in context.selectable_objects:
			if (not obj in pre_selectable_objects):
				curveObj = obj
				break
		bpy.ops.object.select_all(action='DESELECT')
		curveObj.select_set(True)
		bpy.context.view_layer.objects.active = curveObj
		curveObj.data.resolution_u = 1
		bpy.ops.object.convert(target='MESH', keep_original=False)
		pathObj = bpy.context.view_layer.objects.active
		for vert in pathObj.data.vertices:
			if (vert.index % self.dissolve_verts_count == 0):
				vert.select = False
			else:
				vert.select = True
		bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.mesh.dissolve_verts()
		bpy.ops.object.mode_set(mode='OBJECT')
		metas = []
		for vert in pathObj.data.vertices:
			bpy.ops.object.metaball_add(type='BALL', radius=self.radius, align='WORLD', enter_editmode=False, location=vert.co)
			metas.append(bpy.context.view_layer.objects.active)
			metas[-1].data.resolution = self.resolution
		for obj in metas:
			obj.select_set(True)
		context.view_layer.active_layer_collection.collection.objects.unlink(pathObj)
		return {'FINISHED'}

class CreateMeshImitateArmature(bpy.types.Operator):
	bl_idname = "object.create_mesh_imitate_armature"
	bl_label = "Creating an armature to mimic mesh deformation"
	bl_description = "Creates new armature to follow active mesh objects"
	bl_options = {'REGISTER', 'UNDO'}

	bone_length : FloatProperty(name="Bone Length", default=0.1, min=0, max=10, soft_min=0, soft_max=10, step=1, precision=3)
	use_normal : BoolProperty(name="Rotate From Normal", default=False)
	add_edge : BoolProperty(name="Add bones to edge", default=False)
	vert_bone_name : StringProperty(name="Bone name at vertex", default="Vertex")
	edge_bone_name : StringProperty(name="Bone name of edge parts", default="Edge")

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			if (obj.type == 'MESH'):
				return True
		return False
	def execute(self, context):
		pre_active_obj = context.active_object
		for obj in context.selected_objects:
			if (obj.type != 'MESH'):
				self.report(type={'INFO'}, message=obj.name+"mesh object ignored")
				continue
			arm = bpy.data.armatures.new(obj.name+" Armature Imitate")
			arm_obj = bpy.data.objects.new(obj.name+" Armature Imitate", arm)
			context.view_layer.active_layer_collection.collection.objects.link(arm_obj)
			bpy.context.view_layer.objects.active = arm_obj
			bpy.ops.object.mode_set(mode='EDIT')
			bone_names = []
			for vert in obj.data.vertices:
				bone = arm.edit_bones.new(self.vert_bone_name+str(vert.index))
				bone.head = obj.matrix_world @ vert.co
				bone.tail = bone.head + (obj.matrix_world @ vert.normal * self.bone_length)
				bone_names.append(bone.name)
			bpy.ops.object.mode_set(mode='OBJECT')
			for vert, name in zip(obj.data.vertices, bone_names):
				vg = obj.vertex_groups.new(name=name)
				vg.add([vert.index], 1.0, 'REPLACE')
				const = arm_obj.pose.bones[name].constraints.new('COPY_LOCATION')
				const.target = obj
				const.subtarget = vg.name
				if (self.use_normal):
					const_rot = arm_obj.pose.bones[name].constraints.new('COPY_ROTATION')
					const_rot.target = obj
					const_rot.subtarget = vg.name
			bpy.context.view_layer.objects.active = obj
			bpy.ops.object.mode_set(mode='EDIT')
			bpy.ops.object.mode_set(mode='OBJECT')
			bpy.context.view_layer.objects.active = arm_obj
			if (self.use_normal):
				bpy.ops.object.mode_set(mode='POSE')
				bpy.ops.pose.armature_apply()
				bpy.ops.object.mode_set(mode='OBJECT')
			if (self.add_edge):
				edge_bone_names = []
				bpy.ops.object.mode_set(mode='EDIT')
				for edge in obj.data.edges:
					vert0 = obj.data.vertices[edge.vertices[0]]
					vert1 = obj.data.vertices[edge.vertices[1]]
					bone = arm.edit_bones.new(self.edge_bone_name+str(edge.index))
					bone.head = obj.matrix_world @ vert0.co
					bone.tail = obj.matrix_world @ vert1.co
					bone.layers = (False, True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False)
					bone.parent = arm.edit_bones[self.vert_bone_name + str(vert0.index)]
					edge_bone_names.append(bone.name)
				bpy.ops.object.mode_set(mode='OBJECT')
				arm.layers[1] = True
				for edge, name in zip(obj.data.edges, edge_bone_names):
					const = arm_obj.pose.bones[name].constraints.new('STRETCH_TO')
					const.target = arm_obj
					const.subtarget = self.vert_bone_name + str(edge.vertices[1])
		bpy.context.view_layer.objects.active = pre_active_obj
		bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.object.mode_set(mode='OBJECT')
		return {'FINISHED'}

class CreateVertexGroupsArmature(bpy.types.Operator):
	bl_idname = "object.create_vertex_groups_armature"
	bl_label = "Create bone to vertices of vertex groups"
	bl_description = "Create vertex group names bone vertices where vertex group of selected objects that are assigned"
	bl_options = {'REGISTER', 'UNDO'}

	armature_name : StringProperty(name="Armature Name", default="Armature")
	use_vertex_group_name : BoolProperty(name="Bone name to vertex group name", default=True)
	bone_length : FloatProperty(name="Bone Length", default=0.5, min=0, max=10, soft_min=0, soft_max=10, step=1, precision=3)

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			if (obj.type == 'MESH'):
				if (0 < len(obj.vertex_groups)):
					return True
		return False
	def execute(self, context):
		pre_active_obj = context.active_object
		if (not pre_active_obj):
			self.report(type={'ERROR'}, message="There is no active object")
			return {'CANCELLED'}
		pre_mode = pre_active_obj.mode
		for obj in context.selected_objects:
			if (obj.type != 'MESH'):
				self.report(type={'INFO'}, message=obj.name+"A mesh object, ignore")
				continue
			if (len(obj.vertex_groups) <= 0):
				self.report(type={'INFO'}, message=obj.name+"To ignore missing vertex groups")
				continue
			arm = bpy.data.armatures.new(self.armature_name)
			arm_obj = bpy.data.objects.new(self.armature_name, arm)
			context.view_layer.active_layer_collection.collection.objects.link(arm_obj)
			arm_obj.select_set(True)
			bpy.context.view_layer.objects.active = arm_obj
			me = obj.data
			bpy.ops.object.mode_set(mode='EDIT')
			for vert in me.vertices:
				for vg in vert.groups:
					if (0.0 < vg.weight):
						if (self.use_vertex_group_name):
							bone_name = obj.vertex_groups[vg.group].name
						else:
							bone_name = "Bone"
						bone = arm.edit_bones.new(bone_name)
						vert_co = obj.matrix_world @ vert.co
						vert_no = obj.matrix_world.to_quaternion() @ vert.normal * self.bone_length
						bone.head = vert_co
						bone.tail = vert_co + vert_no
			bpy.ops.object.mode_set(mode='OBJECT')
		bpy.context.view_layer.objects.active = pre_active_obj
		bpy.ops.object.mode_set(mode=pre_mode)
		return {'FINISHED'}

class CreateSolidifyEdge(bpy.types.Operator):
	bl_idname = "object.create_solidify_edge"
	bl_label = "Create line drawing by solidify modifier"
	bl_description = "Add to thicken modi contour drawing selection"
	bl_options = {'REGISTER', 'UNDO'}

	use_render : BoolProperty(name="Apply Render", default=False)
	thickness : FloatProperty(name="Thickness of Lines", default=0.01, min=0, max=1, soft_min=0, soft_max=1, step=0.1, precision=3)
	color : FloatVectorProperty(name="Line Color", default=(0.0, 0.0, 0.0), min=0, max=1, soft_min=0, soft_max=1, step=10, precision=3, subtype='COLOR_GAMMA')
	use_rim : BoolProperty(name="Fill face to edge", default=False)
	show_backface_culling : BoolProperty(name="On Backface Culling", default=True)

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			if (obj.type == 'MESH'):
				for mat in obj.material_slots:
					if (mat.material):
						return True
		return False
	def execute(self, context):
		pre_active_obj = context.active_object
		selected_objs = []
		for obj in context.selected_objects:
			if (obj.type == 'MESH'):
				selected_objs.append(obj)
			else:
				self.report(type={'INFO'}, message=obj.name+"mesh object ignored")
		if (len(selected_objs) <= 0):
			self.report(type={'ERROR'}, message="Please run selected mesh object for one or more")
			return {'CANCELLED'}
		for obj in selected_objs:
			pre_mtls = []
			for i in obj.material_slots:
				if (i.material):
					pre_mtls.append(i)
			if (len(pre_mtls) <= 0):
				"""
				self.report(type={'WARNING'}, message=obj.name+"To ignore because material is not assigned")
				continue
				"""
				pass
			bpy.context.view_layer.objects.active = obj

			mtl = bpy.data.materials.new(obj.name+"Lines")
			mtl.diffuse_color = (self.color[0], self.color[1], self.color[2], 1.0)
			mtl.use_nodes = True

			for n in mtl.node_tree.nodes:
				if (n.bl_idname == 'ShaderNodeMaterial'):
					n.material = mtl
			node = mtl.node_tree.nodes.new('ShaderNodeNewGeometry')
			link_input = node.outputs[8]
			for n in mtl.node_tree.nodes:
				if (n.bl_idname == 'ShaderNodeOutputMaterial'):
					link_output = n.inputs[1]
			mtl.node_tree.links.new(link_input, link_output)

			slot_index = len(obj.material_slots)
			bpy.ops.object.material_slot_add()
			slot = obj.material_slots[-1]
			slot.material = mtl

			mod = obj.modifiers.new("Line", 'SOLIDIFY')
			mod.use_flip_normals = True
			if (not self.use_rim):
				mod.use_rim = False
			mod.material_offset = slot_index
			mod.material_offset_rim = slot_index
			mod.offset = 1
			mod.thickness = self.thickness
			if (not self.use_render):
				mod.show_render = False
		bpy.context.view_layer.objects.active = pre_active_obj
		context.space_data.shading.show_backface_culling = self.show_backface_culling
		return {'FINISHED'}
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

##################################
# オペレーター(レンダリング制限) #
##################################

class SetRenderHide(bpy.types.Operator):
	bl_idname = "object.set_render_hide"
	bl_label = "Limit Rendering Selected"
	bl_description = "setting does not render selected object"
	bl_options = {'REGISTER', 'UNDO'}

	reverse : BoolProperty(name="No Render", default=True)

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			return True
		return False
	def execute(self, context):
		for obj in context.selected_objects:
			obj.hide_render = self.reverse
		return {'FINISHED'}

class SyncRenderHide(bpy.types.Operator):
	bl_idname = "object.sync_render_hide"
	bl_label = "Or to render \"show / hide\" to sync"
	bl_description = "Synchronize display / hide status and whether or not to render objects in current layer"
	bl_options = {'REGISTER', 'UNDO'}

	isAll : BoolProperty(name="All Objects", default=False)
	use_col_state : BoolProperty(name="apply to hided collection", default=True)

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			return True
		return False
	def execute(self, context):
		if (self.isAll):
			for obj in bpy.data.objects:
				obj.hide_render = obj.hide_get()
		else:
			master_col = context.view_layer.layer_collection
			views = [c for c in master_col.children if not c.exclude and not c.hide_viewport]
			hides = [c for c in master_col.children if not c.exclude and c.hide_viewport]
			for col in views:
				if len(col.children) != 0:
					views = views + [c for c in col.children if not c.exclude and not c.hide_viewport]
					hides = hides + [c for c in col.children if not c.exclude and c.hide_viewport]
			for col in views:
				for ob in col.collection.objects:
					ob.hide_render = ob.hide_get()
			if self.use_col_state:
				for col in hides:
					for ob in col.collection.objects:
						ob.hide_render = True
		return {'FINISHED'}

##########################
# オペレーター(選択制限) #
##########################

class AllResetHideSelect(bpy.types.Operator):
	bl_idname = "object.all_reset_hide_select"
	bl_label = "Clear all selected limits"
	bl_description = "Removes all non-select settings (vice versa)"
	bl_options = {'REGISTER', 'UNDO'}

	reverse : BoolProperty(name="Set Unselect", default=False)

	@classmethod
	def poll(cls, context):
		for obj in bpy.data.objects:
			if (obj.hide_select):
				return True
		return False
	def execute(self, context):
		for obj in bpy.data.objects:
			obj.hide_select = self.reverse
			if (self.reverse):
				obj.select = not self.reverse
		return {'FINISHED'}

class SetUnselectHideSelect(bpy.types.Operator):
	bl_idname = "object.set_unselect_hide_select"
	bl_label = "Limit select to non-selected"
	bl_description = "Cannot select object other than selection of"
	bl_options = {'REGISTER', 'UNDO'}

	reverse : BoolProperty(name="Set Unselect", default=True)
	limit_view : BoolProperty(name="Exclude hided objects", default=True)

	@classmethod
	def poll(cls, context):
		if len(context.selected_objects) > 0:
			return True
		return False
	def execute(self, context):
		master_col = context.view_layer.layer_collection
		views = [c for c in master_col.children if not c.exclude and not c.hide_viewport]
		hides = [c for c in master_col.children if not c.exclude and c.hide_viewport]
		for col in views:
			if len(col.children) != 0:
				views = views + [c for c in col.children if not c.exclude and not c.hide_viewport]
				hides = hides + [c for c in col.children if not c.exclude and c.hide_viewport]
		if (self.limit_view):
			for col in views:
				for ob in col.collection.objects:
					if not ob.hide_get() and not ob.select_get():
						ob.hide_select = self.reverse
		else:
			for col in views:
				for ob in col.collection.objects:
					if not ob.select_get():
						ob.hide_select = self.reverse
			for col in hides:
				for ob in col.collection.objects:
					if not ob.select_get():
						ob.hide_select = self.reverse
		return {'FINISHED'}

class SetHideSelect(bpy.types.Operator):
	bl_idname = "object.set_hide_select"
	bl_label = "Limit Select"
	bl_description = "Can\'t select selected object"
	bl_options = {'REGISTER', 'UNDO'}

	reverse : BoolProperty(name="Set Unselect", default=True)

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			return True
		return False
	def execute(self, context):
		for obj in context.selected_objects:
			obj.hide_select = self.reverse
			if (self.reverse):
				obj.select_set(not self.reverse)
		return {'FINISHED'}

################################
# オペレーター(オブジェクト名) #
################################

class RenameObjectRegularExpression(bpy.types.Operator):
	bl_idname = "object.rename_object_regular_expression"
	bl_label = "Replace object names by regular expression"
	bl_description = "Name of currently selected object replace with regular expressions"
	bl_options = {'REGISTER', 'UNDO'}

	pattern : StringProperty(name="Before replace (regular expressions)", default="")
	repl : StringProperty(name="After", default="")

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			return True
		return False
	def execute(self, context):
		for obj in context.selected_objects:
			try:
				new_name = re.sub(self.pattern, self.repl, obj.name)
			except:
				continue
			obj.name = new_name
		return {'FINISHED'}

class EqualizeObjectNameAndDataName(bpy.types.Operator):
	bl_idname = "object.equalize_objectname_and_dataname"
	bl_label = "Sync object name and data name"
	bl_description = "same object and data names for selected objects"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			return True
		return False
	def execute(self, context):
		for obj in context.selected_objects:
			if (obj and obj.data):
				obj.data.name = obj.name
		return {'FINISHED'}

####################################
# オペレーター(オブジェクトカラー) #
####################################


class ApplyObjectColor(bpy.types.Operator):
	bl_idname = "object.apply_object_color"
	bl_label = "Enable object color + set color"
	bl_description = "Object color of selected object and sets color,"
	bl_options = {'REGISTER', 'UNDO'}

	color : FloatVectorProperty(name="Color", default=(0, 0, 0), min=0, max=1, soft_min=0, soft_max=1, step=10, precision=3, subtype='COLOR_GAMMA')
	use_random : BoolProperty(name="Use Random Colors", default=True)

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			return True
		return False
	def execute(self, context):
		for ar in context.screen.areas:
			if ar.type == "VIEW_3D":
				area = ar
		for sp in area.spaces:
			if sp.type == "VIEW_3D":
				space = sp
		if (self.use_random):
			space.shading.color_type = 'RANDOM'
		else:
			space.shading.color_type = 'OBJECT'
			for obj in context.selected_objects:
				obj.color = (self.color[0], self.color[1], self.color[2], 1)
		return {'FINISHED'}

class ClearObjectColor(bpy.types.Operator):
	bl_idname = "object.clear_object_color"
	bl_label = "Disable object color + set color"
	bl_description = "To disable object color of selected object, sets color"
	bl_options = {'REGISTER', 'UNDO'}

	set_color : BoolProperty(name="Set Color", default=False)
	color : FloatVectorProperty(name="Color", default=(1, 1, 1), min=0, max=1, soft_min=0, soft_max=1, step=10, precision=3, subtype='COLOR_GAMMA')

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			return True
		return False
	def execute(self, context):
		for ar in context.screen.areas:
			if ar.type == "VIEW_3D":
				area = ar
		for sp in area.spaces:
			if sp.type == "VIEW_3D":
				space = sp
		if not self.set_color:
			space.shading.color_type = 'MATERIAL'
		else:
			space.shading.color_type = 'OBJECT'
			for obj in context.selected_objects:
				obj.color = (self.color[0], self.color[1], self.color[2], 1)
		return {'FINISHED'}

####################
# オペレーター(親) #
####################

class ParentSetApplyModifiers(bpy.types.Operator):
	bl_idname = "object.parent_set_apply_modifiers"
	bl_label = "Applied Modifiers and Create Parent"
	bl_description = "Create parent/child relationship after applying modifiers of parent object"
	bl_options = {'REGISTER', 'UNDO'}

	items = [
		('VERTEX', "Vertex", "", 1),
		('VERTEX_TRI', "Vertex (triangle)", "", 2),
		]
	type : EnumProperty(items=items, name="Calculate")

	@classmethod
	def poll(cls, context):
		if (not context.object):
			return False
		if (context.object.type != 'MESH'):
			return False
		if (len(context.selected_objects) != 2):
			return False
		for obj in context.selected_objects:
			if (obj.name != context.object.name):
				if (obj.type == 'MESH'):
					return True
		return False
	def execute(self, context):
		active_obj = context.active_object
		if (not active_obj):
			self.report(type={'ERROR'}, message="There is no active object")
			return {'CANCELLED'}
		if (active_obj.type != 'MESH'):
			self.report(type={'ERROR'}, message="Active is not mesh object")
			return {'CANCELLED'}
		active_obj.select_set(False)
		enable_modifiers = []
		for mod in active_obj.modifiers:
			if (mod.show_viewport):
				enable_modifiers.append(mod.name)
		bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
		active_obj.select_set(True)
		old_me = active_obj.data
		depsgraph = context.evaluated_depsgraph_get()
		object_eval = active_obj.evaluated_get(depsgraph)
		new_me = object_eval.to_mesh()
		if (len(old_me.vertices) != len(new_me.vertices)):
			self.report(type={'WARNING'}, message="May not count changes after applying modifier to wished result")
		#active_obj.data = new_me
		for mod in object_eval.modifiers:
			if (mod.show_viewport):
				mod.show_viewport = False
		bpy.ops.object.parent_set(type=self.type)
		object_eval.to_mesh_clear()
		active_obj.data = old_me
		for name in enable_modifiers:
			active_obj.modifiers[name].show_viewport = True
		active_obj.select_set(False)
		return {'FINISHED'}
		"""
		bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
		active_obj.select_set(True)
		bpy.ops.object.parent_set(type=self.type)
		for name in enable_modifiers:
			active_obj.modifiers[name].show_viewport = True
		return {'FINISHED'}
		"""

########################
# オペレーター(カーブ) #
########################

class CreateRopeMesh(bpy.types.Operator):
	bl_idname = "object.create_rope_mesh"
	bl_label = "Create rope-shaped mesh from curves"
	bl_description = "Creates mesh like rope along curve object is active or snake new"
	bl_options = {'REGISTER', 'UNDO'}

	vertices : IntProperty(name="Number of Vertices", default=32, min=3, soft_min=3, max=999, soft_max=999, step=1)
	radius : FloatProperty(name="Radius", default=0.1, step=1, precision=3, min=0, soft_min=0, max=99, soft_max=99)
	number_cuts : IntProperty(name="Number of Divisions", default=32, min=2, soft_min=2, max=999, soft_max=999, step=1)
	resolution_u : IntProperty(name="Resolution of Curve", default=64, min=1, soft_min=1, max=999, soft_max=999, step=1)

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			if (context.object.type == 'CURVE'):
				return True
		return False
	def execute(self, context):
		for obj in context.selected_objects:
			activeObj = obj
			bpy.context.view_layer.objects.active = obj
			pre_use_stretch = activeObj.data.use_stretch
			pre_use_deform_bounds = activeObj.data.use_deform_bounds
			bpy.ops.object.transform_apply_all()

			bpy.ops.mesh.primitive_cylinder_add(vertices=self.vertices, radius=self.radius, depth=1, end_fill_type='NOTHING', align='WORLD', enter_editmode=True, location=(0, 0, 0), rotation=(0, 1.5708, 0))
			bpy.ops.mesh.select_all(action='DESELECT')
			context.tool_settings.mesh_select_mode = [False, True, False]
			bpy.ops.mesh.select_non_manifold()
			bpy.ops.mesh.select_all(action='INVERT')
			bpy.ops.mesh.subdivide(number_cuts=self.number_cuts, smoothness=0)
			bpy.ops.object.mode_set(mode='OBJECT')

			meshObj = context.active_object
			modi = meshObj.modifiers.new("temp", 'CURVE')
			modi.object = activeObj
			activeObj.data.use_stretch = True
			activeObj.data.use_deform_bounds = True
			activeObj.data.resolution_u = self.resolution_u
			bpy.ops.object.modifier_apply(modifier=modi.name)
			bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')

			activeObj.data.use_stretch = pre_use_stretch
			activeObj.data.use_deform_bounds = pre_use_deform_bounds
		return {'FINISHED'}

class MoveBevelObject(bpy.types.Operator):
	bl_idname = "object.move_bevel_object"
	bl_label = "Bevel object move section"
	bl_description = "Curve beveled objects that move and selection curve section"
	bl_options = {'REGISTER', 'UNDO'}

	items = [
		('START', "Top", "", 1),
		('END', "End", "", 2),
		('CENTER', "Center", "", 3),
		]
	move_position : EnumProperty(items=items, name="Move Location", default='END')
	use_duplicate : BoolProperty(name="Copy Bevel", default=True)
	delete_pre_bevel : BoolProperty(name="Delete original bevel object", default=False)
	tilt : FloatProperty(name="Z Angle", default=0.0, min=-3.14159265359, max=3.14159265359, soft_min=-3.14159265359, soft_max=3.14159265359, step=1, precision=1, subtype='ANGLE')
	use_2d : BoolProperty(name="To 2D Curve", default=True)

	@classmethod
	def poll(cls, context):
		for obj in context.selected_objects:
			if (obj.type == 'CURVE'):
				if (obj.data.bevel_object):
					return True
		return False
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)
	def execute(self, context):
		bpy.ops.object.mode_set(mode='OBJECT')
		selected_objects = context.selected_objects[:]
		delete_objects = {}
		for obj in selected_objects:
			if (obj.type != 'CURVE'):
				self.report(type={'WARNING'}, message=obj.name+" is not curve, ignored")
				continue
			curve = obj.data
			if (not curve.bevel_object):
				self.report(type={'WARNING'}, message=obj.name+"To ignore bevel object has not been set")
				continue
			bevel_object = curve.bevel_object
			if (len(curve.splines) < 1):
				self.report(type={'WARNING'}, message=obj.name+"Ignore missing in these curves")
				continue
			"""
			if (len(curve.splines[0].points) <= 1):
				self.report(type={'WARNING'}, message=obj.name+"segment number is too low and ignore the")
				continue
			"""
			for o in delete_objects:
				if (obj.name == o.name):
					break
			else:
				delete_objects[bevel_object] = bevel_object.users_collection[0]
			if (self.use_duplicate):
				bevel_object.hide_set(False)
				bpy.ops.object.select_all(action='DESELECT')
				bevel_object.select_set(True)
				bpy.ops.object.duplicate()
				bevel_object = context.selected_objects[0]
				curve.bevel_object = bevel_object
			if (self.use_2d):
				bevel_object.data.dimensions = '2D'
				bevel_object.data.fill_mode = 'NONE'
			spline = curve.splines[0]
			if (spline.type == 'NURBS'):
				if (self.move_position == 'START'):
					base_point = obj.matrix_world @ spline.points[0].co
					sub_point = obj.matrix_world @ spline.points[1].co
					tilt = spline.points[0].tilt
				elif (self.move_position == 'END'):
					base_point = obj.matrix_world @ spline.points[-1].co
					sub_point = obj.matrix_world @ spline.points[-2].co
					tilt = spline.points[-1].tilt
				elif (self.move_position == 'CENTER'):
					i = int(len(spline.points) / 2)
					base_point = obj.matrix_world @ spline.points[i].co
					sub_point = obj.matrix_world @ spline.points[i-1].co
					tilt = spline.points[i].tilt
				else:
					self.report(type={'ERROR'}, message="Option value is invalid")
					return {'CANCELLED'}
			elif (spline.type == 'BEZIER'):
				if (self.move_position == 'START'):
					base_point = obj.matrix_world @ spline.bezier_points[0].co
					sub_point = obj.matrix_world @ spline.bezier_points[0].handle_left
					tilt = spline.bezier_points[0].tilt
				elif (self.move_position == 'END'):
					base_point = obj.matrix_world @ spline.bezier_points[-1].co
					sub_point = obj.matrix_world @ spline.bezier_points[-1].handle_left
					tilt = spline.bezier_points[-1].tilt
				elif (self.move_position == 'CENTER'):
					i = int(len(spline.bezier_points) / 2)
					base_point = obj.matrix_world @ spline.bezier_points[i].co
					sub_point = obj.matrix_world @ spline.bezier_points[i-1].handle_left
					tilt = spline.bezier_points[i].tilt
				else:
					self.report(type={'ERROR'}, message="Option value is invalid")
					return {'CANCELLED'}
			else:
				self.report(type={'WARNING'}, message=obj.name+"Will ignore is curve type not supported")
				continue
			base_point.resize_3d()
			sub_point.resize_3d()
			bevel_object.location = base_point

			vec = sub_point - base_point
			vec.normalize()
			up = mathutils.Vector((0,0,1))
			quat = up.rotation_difference(vec)
			eul = quat.to_euler('XYZ')
			#eul.rotate_axis('Z', 3.141592653589793)
			eul.rotate_axis('Z', tilt)
			eul.rotate_axis('Z', self.tilt)
			bevel_object.rotation_mode = 'XYZ'
			bevel_object.rotation_euler = eul.copy()
		if (self.delete_pre_bevel and self.use_duplicate):
			for obj in delete_objects.keys():
				try:
					delete_objects[obj].objects.unlink(obj)
				except RuntimeError:
					pass
		bpy.ops.object.select_all(action='DESELECT')
		for obj in selected_objects:
			obj.data.bevel_object.select_set(True)
		return {'FINISHED'}

################
# サブメニュー #
################

class RenderHideMenu(bpy.types.Menu):
	bl_idname = "VIEW3D_MT_object_specials_render_hide"
	bl_label = "Rendering Limit"
	bl_description = "Menu object rendering limits involved"

	def draw(self, context):
		self.layout.operator(SetRenderHide.bl_idname, text="Limit Rendering Selected", icon="PLUGIN").reverse = True
		self.layout.operator('object.isolate_type_render')
		self.layout.separator()
		self.layout.operator(SetRenderHide.bl_idname, text="Allow Rendering Selected", icon="PLUGIN").reverse = False
		self.layout.operator('object.hide_render_clear_all')
		self.layout.separator()
		self.layout.operator(SyncRenderHide.bl_idname, icon="PLUGIN")

class HideSelectMenu(bpy.types.Menu):
	bl_idname = "VIEW3D_MT_object_specials_hide_select"
	bl_label = "Select Limit"
	bl_description = "Menu selection limits relationships between objects"

	def draw(self, context):
		self.layout.operator(SetHideSelect.bl_idname, text="Limit Select", icon="PLUGIN").reverse = True
		self.layout.operator(SetUnselectHideSelect.bl_idname, icon="PLUGIN").reverse = True
		self.layout.separator()
		self.layout.operator(AllResetHideSelect.bl_idname, icon="PLUGIN").reverse = False

class ObjectNameMenu(bpy.types.Menu):
	bl_idname = "VIEW3D_MT_object_specials_object_name"
	bl_label = "Object Name"
	bl_description = "Object Name of Menu"

	def draw(self, context):
		self.layout.operator(RenameObjectRegularExpression.bl_idname, icon="PLUGIN")
		self.layout.operator(EqualizeObjectNameAndDataName.bl_idname, icon="PLUGIN")

class ObjectColorMenu(bpy.types.Menu):
	bl_idname = "VIEW3D_MT_object_specials_object_color"
	bl_label = "Object Color"
	bl_description = "Object color operators menu"

	def draw(self, context):
		self.layout.operator(ApplyObjectColor.bl_idname, icon="PLUGIN")
		self.layout.operator(ClearObjectColor.bl_idname, icon="PLUGIN")

class ParentMenu(bpy.types.Menu):
	bl_idname = "VIEW3D_MT_object_specials_parent"
	bl_label = "Parent/Child Relation"
	bl_description = "Parent/Child Menu"

	def draw(self, context):
		self.layout.operator(ParentSetApplyModifiers.bl_idname, icon="PLUGIN", text="Modifiers apply => + vertex (triangle)").type = 'VERTEX_TRI'

class CurveMenu(bpy.types.Menu):
	bl_idname = "VIEW3D_MT_object_specials_curve"
	bl_label = "Curve"
	bl_description = "Curve Operators"

	def draw(self, context):
		self.layout.operator(CreateRopeMesh.bl_idname, icon="PLUGIN")
		self.layout.operator(MoveBevelObject.bl_idname, icon="PLUGIN")

class SpecialsMenu(bpy.types.Menu):
	bl_idname = "VIEW3D_MT_object_specials_specials"
	bl_label = "Special Processing"
	bl_description = "Special actions menu"

	def draw(self, context):
		self.layout.operator(CreateVertexToMetaball.bl_idname, icon="PLUGIN")
		self.layout.operator(AddGreasePencilPathMetaballs.bl_idname, icon="PLUGIN")
		self.layout.separator()
		self.layout.operator(CreateMeshImitateArmature.bl_idname, icon="PLUGIN")
		self.layout.operator(CreateVertexGroupsArmature.bl_idname, icon="PLUGIN")
		self.layout.separator()
		self.layout.operator(CreateSolidifyEdge.bl_idname, icon="PLUGIN")

################
# クラスの登録 #
################

classes = [
	VertexGroupTransferWeightObjmode,
	ToggleSmooth,
	VertexGroupTransfer,
	VertexGroupAverageAll,
	CreateVertexToMetaball,
	AddGreasePencilPathMetaballs,
	CreateMeshImitateArmature,
	CreateVertexGroupsArmature,
	CreateSolidifyEdge,
	SetRenderHide,
	SyncRenderHide,
	AllResetHideSelect,
	SetUnselectHideSelect,
	SetHideSelect,
	RenameObjectRegularExpression,
	EqualizeObjectNameAndDataName,
	ApplyObjectColor,
	ClearObjectColor,
	ParentSetApplyModifiers,
	CreateRopeMesh,
	MoveBevelObject,
	RenderHideMenu,
	HideSelectMenu,
	ObjectNameMenu,
	ObjectColorMenu,
	ParentMenu,
	CurveMenu,
	SpecialsMenu
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
		self.layout.menu(RenderHideMenu.bl_idname, icon="PLUGIN")
		self.layout.menu(HideSelectMenu.bl_idname, icon="PLUGIN")
		self.layout.separator()
		self.layout.menu(ObjectNameMenu.bl_idname, icon="PLUGIN")
		self.layout.menu(ObjectColorMenu.bl_idname, icon="PLUGIN")
		self.layout.menu(ParentMenu.bl_idname, icon="PLUGIN")
		self.layout.separator()
		self.layout.menu(CurveMenu.bl_idname, icon="PLUGIN")
		self.layout.separator()
		self.layout.operator(ToggleSmooth.bl_idname, icon="PLUGIN")
		self.layout.separator()
		self.layout.operator(VertexGroupTransfer.bl_idname, icon="PLUGIN")
		self.layout.operator(VertexGroupAverageAll.bl_idname, icon="PLUGIN")
		self.layout.separator()
		self.layout.menu(SpecialsMenu.bl_idname, icon="PLUGIN")
	if (context.preferences.addons[__name__.partition('.')[0]].preferences.use_disabled_menu):
		self.layout.separator()
		self.layout.operator('wm.toggle_menu_enable', icon='CANCEL').id = __name__.split('.')[-1]
