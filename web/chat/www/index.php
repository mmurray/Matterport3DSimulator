<html>
<head>
<title>Room to Room Dialog</title>

<!-- First include jquery js -->
<script src="//code.jquery.com/jquery-1.12.0.min.js"></script>
<script src="//code.jquery.com/jquery-migrate-1.2.1.min.js"></script>

<!-- Latest compiled and minified JavaScript -->
<script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js" integrity="sha384-Tc5IQib027qvyjSMfHjOMaLkfuWVxZxUPnCJA7l2mCWNIpG9mGCD8wGNIcPD7Txa" crossorigin="anonymous"></script>

<!-- Latest compiled and minified CSS -->
<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css" integrity="sha384-BVYiiSIFeK1dGmJRAkycuHAHRg32OmUcww7on3RYdg4Va+PmSTsz/K68vbdEjh4u" crossorigin="anonymous">

<link rel="stylesheet" href="style.css">

<script type="text/javascript">
// Whether to show debug messages.
var debug = true;

// Global vars for the script
var iv;  // the interval function that polls for Server response
var num_polls_since_last_message = 0;  // the number of times we've polled and gotten no response
// urls the agent uses to communicate with this user
var server_comm_url;
var client_comm_url;

var scan;  // the house index.
var target_obj;  // the target object.
var inst;  // instructions based on target object.
var start_pano;  // the starting panorama.
var end_pano;  // the target, ending panorama.

// Functions related to server-side processing.

// Get the contents of the given url, then delete the underlying file.
// url - url to get from and then delete
// returns - the contents of the url page
function get_and_delete_file(url) {
  var read_url = "manage_files.php?opt=read&fn=" + encodeURIComponent(url) + "&v=" + Math.floor(Math.random() * 999999999).toString();
  var contents = http_get(read_url);
  if (contents == "0") {  // file not written
    return false;
  } else {

    // delete the read file
    var del_url = "manage_files.php?opt=del&fn=" + encodeURIComponent(url);
    success = http_get(del_url);
    if (success == "0") {
      show_error("Failed to delete file '" + url + "' using url '" + del_url + "'.");
    }

    return contents;
  }
}

// Get the contents of the given url.
// url - said url
// Implementation from: https://stackoverflow.com/questions/247483/http-get-request-in-javascript
function http_get(url)
{
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.open("GET", url, false); // false for synchronous request
    xmlHttp.send(null);
    return xmlHttp.responseText;
}

// Check whether the given url returns a 404.
// url - the url to check
// returns bool
function url_exists(url) {
  var check_url = "manage_files.php?opt=exists&fn=" + encodeURIComponent(url);
  var exists = http_get(check_url);
  if (exists == "1") {
    return true;
  } else {
    return false;
  }
}

// Functions related to client-side processing.

// ----------
// Setters.

function set_house(v) {
  add_debug("set_house called with '" + v + "'");
  scan = v;
}

function set_target_obj(v) {
  add_debug("set_target_obj called with '" + v + "'");
  target_obj = v;
  inst = "Find the " + target_obj + " and take a picture of it.";
}

function set_start_pano(v) {
  add_debug("set_start_pano called with '" + v + "'");
  start_pano = v;
}

function set_end_pano(v) {
  add_debug("set_end_pano called with '" + v + "'");
  end_pano = v;
}

// ----------
// Chat interface.

function show_chat() {
  add_debug("show_chat called");
  $('#dialog_div').show();
}

// Enable the user text input.
function enable_chat() {
  add_debug("enable_chat called");
  $('#user_input').prop("disabled", false);
  $('#user_input').focus();
  $('#user_say').prop("disabled", false);
}

// Disable user text input.
function disable_chat() {
  add_debug("disable_chat called");
  $('#user_input').prop("disabled", true);
  $('#user_say').prop("disabled", true);
}

// Add a chat to either the user or partner dialog row and open the next row for typing.
function add_chat(message, speaker) {
  add_debug("add_chat called with " + speaker + " and " + message);
  var table = $('#dialog_table');
  var row_type = (speaker == "self" ? "chat_you_row" : "chat_partner_row");
  var markup = "<tr class=\"" + row_type + "\"><td>" + message + "</td></tr>";
  $("#dialog_table tbody").append(markup);
}

// Get user input chat and send it to the Server.
// d - the directory
// uid - user id
function send_user_chat() {
  add_debug("send_user_chat called");
  var m = $('#user_input').val().toLowerCase().trim();  // read the value, lowercase and strip it
  $('#user_input').val('');  // clear user text
  var data = {type:"update", action:"chat", message:m};
  var url = "manage_files.php?opt=write&fn=" + client_comm_url + "&m=" + encodeURIComponent(JSON.stringify(data));
  var success = http_get(url);
  if (success == "0") {
    show_error("Failed to write file '" + client_comm_url + "' with message contents '" + m + "'.<br>Attempt made with url '" + url + "'.");
  }
  display_aux_message('');
  disable_chat();
}

window.send_user_action = function(t, a, m) {
  add_debug("send_user_action called");
  var data = {type:t, action:a, message:m};
  var url = "manage_files.php?opt=write&fn=" + client_comm_url + "&m=" + encodeURIComponent(JSON.stringify(data));
  var success = http_get(url);
  if (success == "0") {
    show_error("Failed to write file '" + client_comm_url + "' with message contents '" + m + "'.<br>Attempt made with url '" + url + "'.");
  }
}

// ----------
// Navigator interface.

function show_nav() {
  add_debug("show_nav called");
  $('#user_nav_div').show();
  init_nav(scan, start_pano, end_pano, inst);
  $('#shared_instructions').text(inst);
}

function show_mirror_nav() {
  window.setOracleMode();
  add_debug("show_mirror_nav called");
  $('#user_nav_div').show();
  init_nav(scan, start_pano, end_pano, inst);
  $('#shared_instructions').text(inst);
}

function update_mirror_nav(msg) {
  update_oracle_camera(msg);
}

function enable_nav() {
  add_debug("enable_nav called");
  $('#user_nav').prop("disabled", false);
  $('#user_nav_end').prop("disabled", false);
  window.enable_nav_controls();
}

function disable_nav() {
  add_debug("disable_nav called");
  $('#user_nav').prop("disabled", true);
  $('#user_nav_end').prop("disabled", true);
  window.disable_nav_controls();
}

function send_user_end(d, uid) {
  add_debug("send_user_end called");
  var data = {type:"update", action:"end"};
  var url = "manage_files.php?opt=write&fn=" + client_comm_url + "&m=" + encodeURIComponent(JSON.stringify(data));
  var success = http_get(url);
  if (success == "0") {
    show_error("Failed to write file '" + client_comm_url + "' with message contents '" + m + "'.<br>Attempt made with url '" + url + "'.");
  }
  disable_chat();
  display_aux_message('');
}

// ----------
// Gold view interface.

function show_gold_view() {
  add_debug("show_gold_view called");
  $('#user_gold_div').show();
}

function enable_gold_view() {
  $('#user_gold').prop("disabled", false);
  $('#user_gold_play').prop("disabled", false);
  $('#skybox_gold').css({display:'block'});
}

function disable_gold_view() {
  add_debug("disable_gold_view called");
  $('#user_gold').prop("disabled", true);
  $('#user_gold_play').prop("disabled", true);
  $('#skybox_gold').css({display:'none'});
}

// ----------
// Misc.

// Enable the end game/get code button.
function enable_get_code() {
  add_debug("enable_get_code called");
  $('#finished_task_div').show();
  $('#finish_task_button').show();
  $('#finish_task_button').prop("disabled", false);
}

// Display an auxiliary information message below the dialog interface.
function display_aux_message(msg) {
  add_debug("display_aux_message called with " + msg);
  $('#auxiliary_text').html(msg);
}

// Display an error message at the bottom of the page.
function show_error(msg) {
  $('#error_text').html(msg);
}

// Display an error message at the bottom of the page.
function add_debug(msg) {
  if (debug) {
    $('#debug_text').html(msg + "<br/>" + $('#debug_text').html());    
  }
}

// Show the displayed end game message, close dialog, and open the payment button.
function end_game(msg) {
  disable_chat();
  display_aux_message(msg);
  enable_get_code();
  clearInterval(iv);
}

// Enable user typing and remove auxiliary info about waiting for a partner.
function begin_game() {
  display_aux_message('Another player connected! Type a word above to start.');
  enable_user_text();
}

// All the logic for communicating with the server goes here.
function poll_for_agent_messages() {

  // Increment time so far if user is unable to respond.
  if ($('#user_say').prop("disabled")) {
    num_polls_since_last_message += 1;
  }

  // Check for communications from the server and take prescribed action.
  var contents = get_and_delete_file(server_comm_url);
  if (contents) {
    num_polls_since_last_message = 0;
    comm = JSON.parse(contents);

    var idx;
    for (idx = 0; idx < comm.length; idx++)
    {
      if (comm[idx].action == "add_chat") {
        add_chat(comm[idx].message, comm[idx].speaker);      
      }
      else if (comm[idx].action == "disable_chat") {
        disable_chat();
      }
      else if (comm[idx].action == "disable_gold_view") {
        disable_gold_view();
      }
      else if (comm[idx].action == "disable_nav") {
        disable_nav();
      }
      else if (comm[idx].action == "enable_chat") {
        enable_chat();
      }
      else if (comm[idx].action == "enable_error_exit") {
        enable_get_code();
      }
      else if (comm[idx].action == "enable_gold_view") {
        enable_gold_view();
      }
      else if (comm[idx].action == "enable_nav") {
        enable_nav();
      }
      else if (comm[idx].action == "set_aux") {
        display_aux_message(comm[idx].message);
      }
      else if (comm[idx].action == "set_end_pano") {
        set_end_pano(comm[idx].value);
      }
      else if (comm[idx].action == "set_house") {
        set_house(comm[idx].value);
      }
      else if (comm[idx].action == "set_start_pano") {
        set_start_pano(comm[idx].value);
      }
      else if (comm[idx].action == "set_target_obj") {
        set_target_obj(comm[idx].value);
      }
      else if (comm[idx].action == "show_chat") {
        show_chat();
      }
      else if (comm[idx].action == "show_gold_view") {
        show_gold_view();
      }
      else if (comm[idx].action == "show_mirror_nav") {
        show_mirror_nav();
      }
      else if (comm[idx].action == "show_nav") {
        show_nav();
      }
      
      else if (comm[idx].action == "update_mirror_nav") {
        update_mirror_nav(comm[idx].message);
      }
      else {
        show_error("Unrecognized comm action " + comm[idx].action)
      }
    }
  }

  // We poll every 1 seconds (1000 ms); if polling has gone on with no messages for
  // three minutes (internal timeouts are 2), allow ending.
  if (num_polls_since_last_message >= 180) {
    end_game("It looks like something went wrong on our end; sorry about that! You can end the HIT and recieve payment.");
  }

}

// Start the game.
function start_task(d, uid) {

  // Show display.
  $('#inst_div').hide();
  $('#start_game_button').prop("disabled", true);
  $('#interaction_div').show();
  display_aux_message("Waiting on another player to connect...");

  // Start infinite, 5 second poll for server feedback that ends when action message is shown.
  server_comm_url = d + uid + ".server.json";
  client_comm_url = d + uid + ".client.json";
  iv = setInterval(poll_for_agent_messages, 1000);
}

</script>

<script src="https://code.jquery.com/jquery-3.1.0.min.js" integrity="sha256-cCueBR6CsyA4/9szpPfrX3s49M9vUU5BgtiJj06wt/s=" crossorigin="anonymous"></script>
<script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.0.3/js/bootstrap.min.js" integrity="sha384-s1ITto93iSMDxlp/79qhWHi+LsIi9Gx6yL+cOKDuymvihkfol83TYbLbOw+W/wv4" crossorigin="anonymous"></script>
<script type="text/javascript" crossorigin="anonymous" src="https://cdnjs.cloudflare.com/ajax/libs/d3/4.10.2/d3.min.js"></script>
<script type="text/javascript" crossorigin="anonymous" src="https://cdnjs.cloudflare.com/ajax/libs/three.js/104/three.min.js"></script>
<script type="text/javascript" crossorigin="anonymous" src="https://cdnjs.cloudflare.com/ajax/libs/tween.js/16.3.5/Tween.min.js"></script>
<script type="text/javascript" src="<? echo(getenv("JS_PREFIX")); ?>js/RequestAnimationFrame.js"></script>
<script type="text/javascript" src="<? echo(getenv("JS_PREFIX")); ?>js/Detector.js"></script>
<script type="text/javascript" src="<? echo(getenv("JS_PREFIX")); ?>js/PTZCameraControls.js"></script>
<script type="text/javascript" src="<? echo(getenv("JS_PREFIX")); ?>js/Matterport3D.js"></script>
<script type="text/javascript" src="<? echo(getenv("JS_PREFIX")); ?>js/HIT.js"></script>
<script type="text/javascript">
window.R2R_DATA_PREFIX="<? echo(getenv("R2R_DATA_PREFIX") ?: "R2R_data/"); ?>";
window.CONNECTIVITY_DATA_PREFIX="<? echo(getenv("CONNECTIVITY_DATA_PREFIX") ?: "connectivity/"); ?>";
window.MATTERPORT_DATA_PREFIX="<? echo(getenv("MATTERPORT_DATA_PREFIX") ?: "data/"); ?>";
window.MAX_GOLD_LENGTH=<? echo(getenv("MAX_GOLD_LENGTH") ?: 5); ?>;
</script>

</head>

<body>
<div id="container">

<?php
require_once('functions.php');

$d = 'client/';

# This is a new landing, so we need to set up the task and call the Server to make an instance.
if (!isset($_POST['uid'])) {
  $uid = uniqid();
  $client_comm_url = $d . $uid . '.client.json';
  $data = array("type" => "new");
  write_file($client_comm_url, json_encode($data), 'Could not create file to register user with the Server.');

  # Show instructions.
  $inst = "<p>INSTRUCTIONS</p><br/>";
  ?>
  <div class="row" id="inst_div">
    <div class="col-md-12">
      <?php echo $inst;?>
      <button class="btn" id="start_game_button" onclick="start_task('<?php echo $d;?>', '<?php echo $uid;?>')">Start Game</button>
      </form>
    </div>
  </div>
  <?php
}
?>

<div id="interaction_div" style="display:none;">
  <div class="row">
    <div class="col-md-6">
      <div id="user_nav_div" style="display:none;">
        <figure style="display: inline-block; width: 100%;"><canvas id="skybox" style="width:100%; height:auto; display: block; margin: 0 auto;"> </canvas></figure>
        <p>
          When you have found the target object, click 'Take Photo' below.<br/>
          <button class="btn" disabled id="user_nav_end" onclick="send_user_stop('<?php echo $d;?>', '<?php echo $uid;?>')">Take Photo</button>
        </p>
      </div>
      <div id="user_gold_div" style="display:none;">
        <figure style="display: inline-block; width: 100%;"><canvas id="skybox_gold" style="width:100%; height:auto; display: none; margin: 0 auto;"> </canvas></figure>
        <p>
          <button class="btn" disabled="disabled" id="user_gold_play" onclick="window.play_animation()">Show Best Route</button>
        </p>
      </div>
    </div>
    <div class="col-md-6">
      <div id="dialog_div" style="display:none;">
        <p id="shared_instructions"></p>
        <table id="dialog_table" class="dialog_table">
          <thead><th class="chat_header_row">You
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        Partner</th></thead>
          <tbody></tbody>
        </table>
        <p>
          <input type="text" disabled id="user_input" style="width:100%;" placeholder="your message..." onkeydown="if (event.keyCode == 13) {$('#user_say').click();}"><br/>
          <button class="btn" disabled id="user_say" onclick="send_user_chat('<?php echo $d;?>', '<?php echo $uid;?>')">Send</button>
        </p>
      </div>
    </div>
  </div>
  <div class="row">
    <div class="col-md-12">
      <p id="auxiliary_text" style="color:blue"></p>
    </div>
  </div>
  <div class="row">
    <div class="col-md-12">
      <p id="error_text" style="color:red"></p>
    </div>
  </div>
  <div class="row">
    <div class="col-md-12">
      <p id="debug_text" style="color:purple"></p>
    </div>
  </div>
</div>

<div id="finished_task_div" style="display:none;">
  <div class="row">
    <div class="col-md-12">
      <p>Click the button below to generate your Mechanical Turk code needed to submit the HIT.</p>
      <form action="generate_code.php" method="POST">
        <input type="hidden" name="uid" value="<?php echo $uid;?>">
        <input type="submit" class="btn" id="finish_task_button" value="Get Mechanical Turk code" style="display:none;" disabled>
      </form>
    </div>
  </div>
</div>

</div>

</body>

</html>
