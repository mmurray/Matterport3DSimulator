//var ix = ${ix}   // UNCOMMENT THIS LINE WHEN INTEGRATING WITH AMT
var ix = location.search.split('ix=')[1];   // UNCOMMENT THIS LINE TO RUN UI LOCALLY WITH GULP

var scan;
var curr_image_id;
var curr_image_id_gold;
var goal_image_id;

// declare a bunch of variable we will need later
var camera, camera_pose, scene, controls, renderer, connections, id_to_ix, world_frame, cylinder_frame, cubemap_frame;
var camera_gold, camera_pose_gold, scene_gold, controls_gold, renderer_gold, connections_gold, id_to_ix_gold,
    world_frame_gold, cylinder_frame_gold, cubemap_frame_gold;
var mouse = new THREE.Vector2();
var id, id_gold, last_pose;

var SIZE_X = 960;
var SIZE_Y = 540;
var VFOV = 90;
var ASPECT = SIZE_X/SIZE_Y;
var path;
var oracle_mode = false;
var playing = false;
var optimal_policy;
var anim_org_pos;
var anim_org_rot;
var anim_org_img;
var reversed_policies = {};


window.setOracleMode = function() {
  oracle_mode = true;
  gold_skybox_init();
};

var matt = new Matterport3D("");

window.init_nav = function() {
  matt.loadJson(window.R2R_DATA_PREFIX + '/R2R_train.json').then(function(data){
    task = data[ix.toString()];
    scan = task['scan'];
    curr_image_id = task['path'][0];
    curr_image_id_gold = task['path'][0];
    goal_image_id = task['path'][task['path'].length - 1];
    instructions = task['instructions'][0];
    $('#instr').text(instructions);
    skybox_init();
    load_connections(scan, curr_image_id);

    if (oracle_mode) {
      matt.loadJson(window.MATTERPORT_DATA_PREFIX + '/v1/scans/'+scan+'/policies/'+goal_image_id+'.json').then(function(policyData){
        optimal_policy = policyData;
        reversed_policies = {};
        $('#user_gold_play').removeAttr('disabled');
      });
    }
  });
};

window.disable_nav_controls = function() {
  controls.enabled=false;
  $('#skybox').css({'opacity': 0.5});
};

window.enable_nav_controls = function() {
  if (!controls) return; // Not initialized yet, just return...
  controls.enabled=true;
  $('#skybox').css({'opacity': 1.0});
};

window.update_oracle_camera = function(msg, gold_only = false) {
  if (!controls) {
    return;
  }

  if (msg.rot) {
    controls.camera.rotation.x = msg.rot._x;
    controls.camera.rotation.y = msg.rot._y;
    render(renderer, scene, camera);

    if (!playing) {
      controls_gold.camera.rotation.x = msg.rot._x;
      controls_gold.camera.rotation.y = msg.rot._y;
      render(renderer_gold, scene_gold, camera_gold);
    }
  }

  function animateCylinderTransition(cylinder_frame, camera, camera_pose, renderer, scene, world_frame, is_gold) {
      var cylinder = cylinder_frame.getObjectByName(msg.img_id);
      cylinder.currentHex = cylinder.material.emissive.getHex();
      cylinder.material.emissive.setHex( 0xff0000 );
      setTimeout(function(){ cylinder.material.emissive.setHex( cylinder.currentHex ); }, 200);
      take_action(msg.img_id, cylinder_frame, camera, camera_pose, renderer, scene, world_frame, is_gold);
    }

  if (msg.img_id != curr_image_id && !gold_only) {
    animateCylinderTransition(cylinder_frame, camera, camera_pose, renderer, scene, world_frame);
  }
  if (msg.img_id != curr_image_id_gold && (gold_only || !playing)) {
    animateCylinderTransition(cylinder_frame_gold, camera_gold, camera_pose_gold, renderer_gold, scene_gold, world_frame_gold, true);
  }
};

// ## Initialize everything
function skybox_init() {
  // test if webgl is supported
  if (! Detector.webgl) Detector.addGetWebGLMessage();

  // create the camera (kinect 2)
  camera = new THREE.PerspectiveCamera(VFOV, ASPECT, 0.01, 1000);
  camera_pose = new THREE.Group();
  camera_pose.add(camera);
  
  // create the Matterport world frame
  world_frame = new THREE.Group();
  
  // create the cubemap frame
  cubemap_frame = new THREE.Group();
  cubemap_frame.rotation.x = -Math.PI; // Adjust cubemap for z up
  cubemap_frame.add(world_frame);
  
  // create the Scene
  scene = new THREE.Scene();
  world_frame.add(camera_pose);
  scene.add(cubemap_frame);

  var light = new THREE.DirectionalLight( 0xFFFFFF, 1 );
  light.position.set(0, 0, 100);
  world_frame.add(light);
  world_frame.add(new THREE.AmbientLight( 0xAAAAAA )); // soft light

  // init the WebGL renderer
  renderer = new THREE.WebGLRenderer({canvas: document.getElementById("skybox"), antialias: true } );
  renderer.setSize(SIZE_X, SIZE_Y);


  controls = new THREE.PTZCameraControls(camera, renderer.domElement);
  controls.minZoom = 1;
  controls.maxZoom = 3.0;
  controls.minTilt = -0.6 * Math.PI / 2;
  controls.maxTilt = 0.6 * Math.PI / 2;
  controls.enableDamping = true;
  controls.panSpeed = -0.25;
  controls.tiltSpeed = -0.25;
  controls.zoomSpeed = 1.5;
  controls.dampingFactor = 0.5;

  controls.addEventListener('select', select);
  controls.addEventListener('change', function() { render(renderer, scene, camera); });
  controls.addEventListener('rotate', log_pose);
  if (oracle_mode) {
    controls.enabled=false;
    controls.dispose();
  }
}

function gold_skybox_init() {
  // create the camera (kinect 2)
  camera_gold = new THREE.PerspectiveCamera(VFOV, ASPECT, 0.01, 1000);
  camera_pose_gold = new THREE.Group();
  camera_pose_gold.add(camera_gold);

  // create the Matterport world frame
  world_frame_gold = new THREE.Group();

  // create the cubemap frame
  cubemap_frame_gold = new THREE.Group();
  cubemap_frame_gold.rotation.x = -Math.PI; // Adjust cubemap for z up
  cubemap_frame_gold.add(world_frame_gold);

  // create the Scene
  scene_gold = new THREE.Scene();
  world_frame_gold.add(camera_pose_gold);
  scene_gold.add(cubemap_frame_gold);

  var light_gold = new THREE.DirectionalLight( 0xFFFFFF, 1 );
  light_gold.position.set(0, 0, 100);
  world_frame_gold.add(light_gold);
  world_frame_gold.add(new THREE.AmbientLight( 0xAAAAAA )); // soft light

  // init the WebGL renderer
  renderer_gold = new THREE.WebGLRenderer({canvas: document.getElementById("skybox_gold"), antialias: true } );
  renderer_gold.setSize(SIZE_X, SIZE_Y);


  controls_gold = new THREE.PTZCameraControls(camera_gold, renderer_gold.domElement);
  controls_gold.minZoom = 1;
  controls_gold.maxZoom = 3.0;
  controls_gold.minTilt = -0.6 * Math.PI / 2;
  controls_gold.maxTilt = 0.6 * Math.PI / 2;
  controls_gold.enableDamping = true;
  controls_gold.panSpeed = -0.25;
  controls_gold.tiltSpeed = -0.25;
  controls_gold.zoomSpeed = 1.5;
  controls_gold.dampingFactor = 0.5;

  controls_gold.addEventListener('change', function() { render(renderer_gold, scene_gold, camera_gold); });

  // controls_gold.enabled=false;
  controls_gold.dispose();
}

function gold_skybox_reinit() {
  // create the camera (kinect 2)
  camera_gold = camera.clone();
  camera_pose_gold = new THREE.Group();
  camera_pose_gold.add(camera_gold);

  // create the Matterport world frame
  world_frame_gold = new THREE.Group();

  // create the cubemap frame
  cubemap_frame_gold = new THREE.Group();
  cubemap_frame_gold.rotation.x = -Math.PI; // Adjust cubemap for z up
  cubemap_frame_gold.add(world_frame_gold);

  // create the Scene
  scene_gold = new THREE.Scene();
  world_frame_gold.add(camera_pose_gold);
  scene_gold.add(cubemap_frame_gold);

  var light_gold = new THREE.DirectionalLight( 0xFFFFFF, 1 );
  light_gold.position.set(0, 0, 100);
  world_frame_gold.add(light_gold);
  world_frame_gold.add(new THREE.AmbientLight( 0xAAAAAA )); // soft light

  // // init the WebGL renderer
  // renderer = new THREE.WebGLRenderer({canvas: document.getElementById("skybox"), antialias: true } );
  // renderer.setSize(SIZE_X, SIZE_Y);

  controls_gold.camera = camera_gold;
  // controls_gold = new THREE.PTZCameraControls(camera_gold, renderer_gold.domElement);
  // controls_gold.minZoom = 1;
  // controls_gold.maxZoom = 3.0;
  // controls_gold.minTilt = -0.6 * Math.PI / 2;
  // controls_gold.maxTilt = 0.6 * Math.PI / 2;
  // controls_gold.enableDamping = true;
  // controls_gold.panSpeed = -0.25;
  // controls_gold.tiltSpeed = -0.25;
  // controls_gold.zoomSpeed = 1.5;
  // controls_gold.dampingFactor = 0.5;
  //
  // controls_gold.camera = controls.camera.clone();
  //
  // controls_gold.addEventListener('change', function() { render(renderer_gold, scene_gold, camera_gold); });
  //
  // controls_gold.enabled=false;
  // controls_gold.dispose();

}

function select(event) {
  var mouse = new THREE.Vector2();
  var raycaster = new THREE.Raycaster();
  var x = renderer.domElement.offsetWidth;
  var y = renderer.domElement.offsetHeight;
  mouse.x = ( event.x / x ) * 2 - 1;
  mouse.y = - ( event.y / y ) * 2 + 1;
  raycaster.setFromCamera( mouse, camera );
  var intersects = raycaster.intersectObjects( cylinder_frame.children );
  if ( intersects.length > 0 ) {
    intersects[0].object.currentHex = intersects[0].object.material.emissive.getHex();
    intersects[0].object.material.emissive.setHex( 0xff0000 );
    image_id = intersects[ 0 ].object.name;
    take_action(image_id, cylinder_frame, camera, camera_pose, renderer, scene, world_frame);
    setTimeout(function(){ intersects[0].object.material.emissive.setHex( intersects[0].object.currentHex ); }, 200);
  }
}


function initialize_data(scan, image_id) {
  // Create a cylinder frame for showing arrows of directions
  cylinder_frame = matt.load_viewpoints(connections);
  cylinder_frame_gold = matt.load_viewpoints(connections);

  if (oracle_mode) {
    cylinder_frame.visible = false;
    cylinder_frame_gold.visible = false;
  }

  // Keep a structure of connection graph
  id_to_ix = {};
  for (var i = 0; i < connections.length; i++) {
    var im = connections[i]['image_id'];
    id_to_ix[im] = i;
  }

  world_frame.add(cylinder_frame);
  if (world_frame_gold) {
    world_frame_gold.add(cylinder_frame_gold);
  }
  matt.loadCubeTexture(cube_urls(scan, image_id)).then(function(texture){

    scene.background = texture;

    if (scene_gold) {
      scene_gold.background = texture;
    }

    move_to(image_id, cylinder_frame, world_frame, true);
    if (cylinder_frame_gold && world_frame_gold) {
      move_to(image_id, cylinder_frame_gold, world_frame_gold, true, true);
    }
  });
}

function reinitialize_data(scan, image_id) {
  // Create a cylinder frame for showing arrows of directions
  if (world_frame_gold) {
    world_frame_gold.add(cylinder_frame_gold);
  }
  scene_gold.background = scene.background;
  move_to(image_id, cylinder_frame_gold, world_frame_gold, true, true);
}

function load_connections(scan, image_id) {
  if (!connections) {
    var pose_url = window.CONNECTIVITY_DATA_PREFIX + "/" + scan + "_connectivity.json";
    d3.json(pose_url, function (error, data) {
      if (error) return console.warn(error);
      connections = data;
      initialize_data(scan, image_id);
    });
  } else {
    initialize_data(scan, image_id);
  }
}

function cube_urls(scan, image_id) {
  var urlPrefix  = window.MATTERPORT_DATA_PREFIX + "/v1/scans/" + scan + "/matterport_skybox_images/" + image_id;
  return [ urlPrefix + "_skybox2_sami.jpg", urlPrefix + "_skybox4_sami.jpg",
      urlPrefix + "_skybox0_sami.jpg", urlPrefix + "_skybox5_sami.jpg",
      urlPrefix + "_skybox1_sami.jpg", urlPrefix + "_skybox3_sami.jpg" ];
}

function move_to(image_id, cylinder_frame, world_frame, isInitial=false, isGold=false) {
  // Adjust cylinder visibility
  var cylinders = cylinder_frame.children;
  for (var i = 0; i < cylinders.length; ++i){
    cylinders[i].visible = isGold && playing ? false : connections[id_to_ix[image_id]]['unobstructed'][i];
  }
  // Correct world frame for individual skybox camera rotation
  var inv = new THREE.Matrix4();
  var cam_pose = cylinder_frame.getObjectByName(image_id);

  inv.getInverse(cam_pose.matrix);
  var ignore = new THREE.Vector3();
  inv.decompose(ignore, world_frame.quaternion, world_frame.scale);
  world_frame.updateMatrix();
  if (!isGold) {
    if (isInitial) {
      set_camera_pose(camera_pose, cam_pose.matrix, cam_pose.height);
    } else {
      set_camera_position(camera_pose, cam_pose.matrix, cam_pose.height);
    }
    render(renderer, scene, camera);
  } else{
    if (isInitial){
      set_camera_pose(camera_pose_gold, cam_pose.matrix, cam_pose.height);
    } else {
      set_camera_position(camera_pose_gold, cam_pose.matrix, cam_pose.height);
    }
    render(renderer_gold, scene_gold, camera_gold);
  }
  if (isGold) {
    curr_image_id_gold = image_id;
  }else {
    curr_image_id = image_id;
  }
  log_pose();

  // Animation
  if (playing) {
    step_forward();
  }
}

function set_camera_pose(camera_pose, matrix4d, height){
  matrix4d.decompose(camera_pose.position, camera_pose.quaternion, camera_pose.scale);
  camera_pose.position.z += height;
  camera_pose.rotateX(Math.PI); // convert matterport camera to webgl camera
}

function set_camera_position(camera_pose, matrix4d, height) {
  var ignore_q = new THREE.Quaternion();
  var ignore_s = new THREE.Vector3();
  matrix4d.decompose(camera_pose.position, ignore_q, ignore_s);
  camera_pose.position.z += height;
}

function get_camera_pose(camera, camera_pose){
  camera.updateMatrix();
  camera_pose.updateMatrix();
  var m = camera.matrix.clone();
  m.premultiply(camera_pose.matrix);
  return m;
}

Math.degrees = function(radians) {
  return radians * 180 / Math.PI;
};

function log_pose() {
  var pose = get_pose_string();
  if (pose !== last_pose) {
    if (!oracle_mode) window.send_user_action("update", "nav", {
      rot: camera.rotation,
      pos: camera.position,
      img_id: curr_image_id
    });
    $('#traj').val($('#traj').val()+','+pose);
    last_pose = pose;
  }
}

function get_pose_string(){
  var m = get_camera_pose(camera, camera_pose);

  // calculate heading
  var rot = new THREE.Matrix3();
  rot.setFromMatrix4(m);
  var cam_look = new THREE.Vector3(0,0,1); // based on matterport camera
  cam_look.applyMatrix3(rot);
  heading = Math.PI/2.0 -Math.atan2(cam_look.y, cam_look.x);
  if (heading < 0) {
    heading += 2.0*Math.PI;
  }

  // calculate elevation
  elevation = -Math.atan2(cam_look.z, Math.sqrt(Math.pow(cam_look.x,2) + Math.pow(cam_look.y,2)))
  
  return "("+curr_image_id+","+Math.degrees(heading)+","+Math.degrees(elevation)+")";
}

function take_action(image_id, cylinder_frame, camera, camera_pose, renderer, scene, world_frame, isGold) {
  var texture_promise = matt.loadCubeTexture(cube_urls(scan, image_id)); // start fetching textures
  var target = cylinder_frame.getObjectByName(image_id);

  // Camera up vector
  var camera_up = new THREE.Vector3(0,1,0);
  var camera_look = new THREE.Vector3(0,0,-1);
  var camera_m = get_camera_pose(camera, camera_pose);
  var zero = new THREE.Vector3(0,0,0);
  camera_m.setPosition(zero);
  camera_up.applyMatrix4(camera_m);
  camera_up.normalize();
  camera_look.applyMatrix4(camera_m);
  camera_look.normalize();

  // look direction
  var look = target.position.clone();
  look.sub(camera_pose.position);
  look.projectOnPlane(camera_up);
  look.normalize();
  // Simplified - assumes z is zero
  var rotate = Math.atan2(look.y,look.x) - Math.atan2(camera_look.y,camera_look.x);
  if (rotate < -Math.PI) rotate += 2*Math.PI;
  if (rotate > Math.PI) rotate -= 2*Math.PI;

  var target_y = camera.rotation.y + rotate;
  var rotate_tween = new TWEEN.Tween({
    x: camera.rotation.x,
    y: camera.rotation.y,
    z: camera.rotation.z})
  .to( {
    x: camera.rotation.x,
    y: target_y,
    z: 0 }, 2000*Math.abs(rotate) )
  .easing( TWEEN.Easing.Cubic.InOut)
  .onUpdate(function() {
    camera.rotation.x = this.x;
    camera.rotation.y = this.y;
    camera.rotation.z = this.z;
    render(renderer, scene, camera);
  });
  var new_vfov = VFOV*0.95;
  var zoom_tween = new TWEEN.Tween({
    vfov: VFOV})
  .to( {vfov: new_vfov }, 500 )
  .easing(TWEEN.Easing.Cubic.InOut)
  .onUpdate(function() {
    camera.fov = this.vfov;
    camera.updateProjectionMatrix();
    render(renderer, scene, camera);
  })
  .onComplete(function(){
    cancelAnimationFrame(isGold ? id_gold : id);
    // cancelAnimationFrame(id);
    texture_promise.then(function(texture) {
      scene.background = texture; 
      camera.fov = VFOV;
      camera.updateProjectionMatrix();
      // move_to(image_id);
      move_to(image_id, cylinder_frame, world_frame, false, isGold)
    });
  });
  rotate_tween.chain(zoom_tween);
  if(isGold) {
    animate_gold();
  } else {
    if (!playing) {
      animate();
    }
  }
  rotate_tween.start();
}

// Display the Scene
function render(renderer, scene, camera) {
  renderer.render(scene, camera);
}

// tweening
function animate() {
  id = requestAnimationFrame( animate );
  TWEEN.update();
}

function animate_gold() {
  id_gold = requestAnimationFrame( animate );
  TWEEN.update();
}


// Gold path animation
window.play_animation = function() {
  if (!playing){
    anim_org_pos = controls_gold.camera.position;
    anim_org_rot = controls_gold.camera.rotation;
    anim_org_img = curr_image_id_gold;

    var cylinders = cylinder_frame_gold.children;
    for (var i = 0; i < cylinders.length; ++i){
      cylinders[i].visible = false;
    }

    if (!reversed_policies[curr_image_id_gold]) {
      reversed_policies[curr_image_id_gold] = true;
      optimal_policy[curr_image_id_gold].reverse();
    }

    path = optimal_policy[curr_image_id_gold];
    // path.shift(); // remove the first node because we're already there
    document.getElementById("user_gold_play").disabled = true;
    step = 0;
    playing = true;
    step_forward();
  }
};

function step_forward(){
  if (step >= path.length-1) {
    playing = false;
    step = 0;

    setTimeout(function() {
      gold_skybox_reinit();
      reinitialize_data(scan, curr_image_id);
      window.update_oracle_camera({
        img_id: curr_image_id,
        rot: {_x: controls.camera.rotation.x, _y: controls.camera.rotation.y}
      }, true);
      // move_to(curr_image_id, cylinder_frame_gold, world_frame_gold, true, true);
      // load_connections(scan, path[0]);

      // controls_gold.camera.position = anim_org_pos;
      // controls_gold.camera.rotation = anim_org_rot;
      // render(renderer_gold, scene_gold, camera_gold);

      // move_to(anim_org_img, cylinder_frame_gold, world_frame_gold, false, true);

      // window.update_oracle_camera({img_id: path[step]}, true);
      document.getElementById("user_gold_play").disabled = false;
    }, 3000);
    // var cylinders = cylinder_frame_gold.children;
    // for (var i = 0; i < cylinders.length; ++i){
    //   cylinders[i].visible = connections[id_to_ix[curr_image_id_gold]]['unobstructed'][i];
    // }
  } else {
    step += 1;
    window.update_oracle_camera({img_id: path[step]}, true);
  }
};
