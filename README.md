# Simplify Service Layer

helper for declarative backend service layer.

## UseCase Example

```python
class UserService extends Service {

    def __init__(self, UserRepository user_repository):
        self.user_repository = user_repository

    """
    names declaration be used in validation error message
    """
    @staticmethod
    def getNames():
        return {
            # basic example
            'token' => 'authorized token',
            # dictionary type data key must have '[...]' for subkey naming
            'auth_user' => 'authorized user[...]',
            # nested bound name with '{{keyName}}'
            'user_profile' => 'profile[...] for {{auth_user}}',
        }

    """
    callbacks declaration be run after validation check is passed
    """
    @staticmethod
    def getCallbacks():
        # called after `auth_user` validation check is passed
        def auth_user__session(auth_user):
            # session
            Session.setData('auth_user', auth_user)

        # called after `auth_user` validation check is passed
        def auth_user__logging(auth_user):
            # logging
            Log.write('user id:'+auth_user.getId()+' logged in')

    """
    loaders declaration be used for loading data
    """
    @staticmethod
    def getLoaders():
        # injected `user_repository` value take from instance properties
        # injected `jwe` value take from loaded data
        def auth_user(jwe, user_repository):
          return user_repository.findById(jwe.sid)

        # injected `token` value take from init input token parameter
        def jwe(token):
          return new JWE(token)

        # result key must be exists
        # result key is output value of service.run
        def result(auth_user):
          return auth_user

    """
    rule lists declaration be used for validation check
    """
    @staticmethod
    def getRuleLists():
        return {
          # ...
        }
}
```
