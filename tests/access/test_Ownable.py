import pytest
from signers import MockSigner
from utils import (
    ZERO_ADDRESS,
    assert_event_emitted,
    get_contract_class,
    cached_contract,
    State,
    Account,
    assert_revert
)


signer = MockSigner(123456789987654321)

@pytest.fixture(scope='module')
def contract_classes():
    return (
        Account.get_class,
        get_contract_class('Ownable')
    )


@pytest.fixture(scope='module')
async def ownable_init(contract_classes):
    account_cls, ownable_cls = contract_classes
    starknet = await State.init()
    owner = await Account.deploy(signer.public_key)
    ownable = await starknet.deploy(
        contract_class=ownable_cls,
        constructor_calldata=[owner.contract_address]
    )
    not_owner = await Account.deploy(signer.public_key)
    return starknet.state, ownable, owner, not_owner


@pytest.fixture
def ownable_factory(contract_classes, ownable_init):
    account_cls, ownable_cls = contract_classes
    state, ownable, owner, not_owner = ownable_init
    _state = state.copy()
    owner = cached_contract(_state, account_cls, owner)
    ownable = cached_contract(_state, ownable_cls, ownable)
    not_owner = cached_contract(_state, account_cls, not_owner)
    return ownable, owner, not_owner


@pytest.mark.asyncio
async def test_constructor(ownable_factory):
    ownable, owner, _ = ownable_factory
    expected = await ownable.owner().call()
    assert expected.result.owner == owner.contract_address


@pytest.mark.asyncio
async def test_transferOwnership(ownable_factory):
    ownable, owner, _ = ownable_factory
    new_owner = 123
    await signer.send_transaction(owner, ownable.contract_address, 'transferOwnership', [new_owner])
    executed_info = await ownable.owner().call()
    assert executed_info.result == (new_owner,)


@pytest.mark.asyncio
async def test_transferOwnership_emits_event(ownable_factory):
    ownable, owner, _ = ownable_factory
    new_owner = 123
    tx_exec_info = await signer.send_transaction(owner, ownable.contract_address, 'transferOwnership', [new_owner])

    assert_event_emitted(
        tx_exec_info,
        from_address=ownable.contract_address,
        name='OwnershipTransferred',
        data=[
            owner.contract_address,
            new_owner
        ]
    )


@pytest.mark.asyncio
async def test_renounceOwnership(ownable_factory):
    ownable, owner, _ = ownable_factory
    await signer.send_transaction(owner, ownable.contract_address, 'renounceOwnership', [])
    executed_info = await ownable.owner().call()
    assert executed_info.result == (ZERO_ADDRESS,)

@pytest.mark.asyncio
async def test_contract_without_owner(ownable_factory):
    ownable, owner, _ = ownable_factory
    await signer.send_transaction(owner, ownable.contract_address, 'renounceOwnership', [])

    # Protected function should not be called from zero address
    await assert_revert(
        ownable.protected_function().invoke(),
        reverted_with="Ownable: caller is the zero address"
    )

@pytest.mark.asyncio
async def test_contract_caller_not_owner(ownable_factory):
    ownable, owner, not_owner = ownable_factory

    # Protected function should only be called from owner
    await assert_revert(
        signer.send_transaction(not_owner, ownable.contract_address, 'protected_function', []),
        reverted_with="Ownable: caller is not the owner"
    )


@pytest.mark.asyncio
async def test_renounceOwnership_emits_event(ownable_factory):
    ownable, owner, _ = ownable_factory
    tx_exec_info = await signer.send_transaction(owner, ownable.contract_address, 'renounceOwnership', [])

    assert_event_emitted(
        tx_exec_info,
        from_address=ownable.contract_address,
        name='OwnershipTransferred',
        data=[
            owner.contract_address,
            ZERO_ADDRESS
        ]
    )
